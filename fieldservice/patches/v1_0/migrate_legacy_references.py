# Copyright (c) 2026, itsdave GmbH and contributors
# For license information, please see license.txt

"""Move the app's four scattered reference mechanisms onto one table.

Until now a service report could point at something in four ways:

* `ofork_ticket_number` (header) and `otrs_ticket` / `otrs_article`
  (positions) — the OTRS era, removed from the DocTypes when the app was
  made tenant neutral. Frappe does not drop database columns on migrate,
  so the data is still there, orphaned.
* `reference_document_type` / `reference_document_id` — a single ERP
  document, picked from a list in Fieldservice Settings.

All of them are collected into `Service Report.references`, described by
`Reference Source` master records: documents keep a real Dynamic Link,
external records become an ID under a source that knows the URL template.

The legacy columns are deliberately left in place: they are the only
backup of this data until the migration has been reviewed on the live
system, and `msp` still reads `otrs_article` in one query. Dropping them
is a separate, later step.
"""

import frappe

from fieldservice.setup import seed_reference_sources

LEGACY_SYSTEM = "OTRS (Alt)"


def execute():
	columns = {
		"sr_ofork": _has_column("Service Report", "ofork_ticket_number"),
		"work_ticket": _has_column("Service Report Work", "otrs_ticket"),
		"work_article": _has_column("Service Report Work", "otrs_article"),
		"sr_document": _has_column("Service Report", "reference_document_id"),
	}

	positions = _legacy_positions(columns)
	header_tickets = _legacy_header_tickets(columns)
	documents = _legacy_documents(columns)

	if not (positions or header_tickets or documents):
		seed_reference_sources()
		return

	migrated_positions = _migrate_positions(positions)

	rows = _external_rows(header_tickets, positions)
	created = 0
	if rows:
		created += _write_rows(rows, _ensure_legacy_system(), external=True)
	if documents:
		created += _write_document_rows(documents)

	# Give the site the standard document sources it could not have had before.
	seed_reference_sources()

	frappe.db.commit()
	print(
		f"fieldservice: migrated {migrated_positions} legacy positions "
		f"and created {created} reference rows"
	)


def _has_column(doctype, column):
	return column in frappe.db.get_table_columns(doctype)


def _legacy_positions(columns):
	"""[{name, parent, ticket, entry}] for work positions carrying legacy data."""
	if not (columns["work_ticket"] or columns["work_article"]):
		return []

	ticket = "`otrs_ticket`" if columns["work_ticket"] else "NULL"
	article = "`otrs_article`" if columns["work_article"] else "NULL"
	where = " OR ".join(
		f"({col} IS NOT NULL AND {col} != '')" for col in (ticket, article) if col != "NULL"
	)

	return frappe.db.sql(
		f"""
		SELECT name, parent, {ticket} AS ticket, {article} AS entry
		FROM `tabService Report Work`
		WHERE {where}
		""",
		as_dict=True,
	)


def _legacy_header_tickets(columns):
	"""{report: ticket} for reports carrying a legacy header ticket number."""
	if not columns["sr_ofork"]:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT name, `ofork_ticket_number` AS ticket
		FROM `tabService Report`
		WHERE `ofork_ticket_number` IS NOT NULL AND `ofork_ticket_number` != ''
		""",
		as_dict=True,
	)
	return {r.name: r.ticket.strip() for r in rows if (r.ticket or "").strip()}


def _legacy_documents(columns):
	"""[{report, doctype, name}] for reports pointing at a single ERP document."""
	if not columns["sr_document"]:
		return []

	rows = frappe.db.sql(
		"""
		SELECT name AS report, `reference_document_type` AS doctype,
		       `reference_document_id` AS document
		FROM `tabService Report`
		WHERE `reference_document_id` IS NOT NULL AND `reference_document_id` != ''
		""",
		as_dict=True,
	)
	return [r for r in rows if r.doctype and frappe.db.exists("DocType", r.doctype)]


def _ensure_legacy_system():
	"""A disabled source for the OTRS data — no URL, that system is gone."""
	if frappe.db.exists("Reference Source", LEGACY_SYSTEM):
		return LEGACY_SYSTEM

	doc = frappe.get_doc(
		{
			"doctype": "Reference Source",
			"title": LEGACY_SYSTEM,
			"source_type": "External System",
			"enabled": 0,
			"is_default": 0,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _ensure_document_source(doctype):
	"""A document source per referenced DocType, reused if it already exists."""
	existing = frappe.db.get_value(
		"Reference Source", {"source_type": "Document", "document_type": doctype}, "name"
	)
	if existing:
		return existing

	title = doctype if not frappe.db.exists("Reference Source", doctype) else f"{doctype} (Bezug)"
	doc = frappe.get_doc(
		{
			"doctype": "Reference Source",
			"title": title,
			"source_type": "Document",
			"document_type": doctype,
			"enabled": 1,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _external_rows(header_tickets, positions):
	"""{report: {tickets}} — the table lists which records a report touched;
	the entry (article) stays on the position it belongs to, unambiguous."""
	wanted = {}
	for report, ticket in header_tickets.items():
		wanted.setdefault(report, set()).add(ticket)
	for row in positions:
		ticket = (row.ticket or "").strip()
		if ticket:
			wanted.setdefault(row.parent, set()).add(ticket)
	return wanted


def _migrate_positions(positions):
	"""Write legacy ticket/article onto the position's own fields."""
	count = 0
	for row in positions:
		values = {}
		if (row.ticket or "").strip():
			values["reference_id"] = row.ticket.strip()
		if (row.entry or "").strip():
			values["reference_entry"] = row.entry.strip()
		if not values:
			continue
		frappe.db.set_value("Service Report Work", row.name, values, update_modified=False)
		count += 1
	return count


def _write_rows(wanted, source, external):
	"""One row per report and distinct external reference."""
	reports = list(wanted)
	docstatus = _docstatus_by_report(reports)
	existing, max_idx = _existing_rows(reports)

	created = 0
	for report, references in wanted.items():
		if report not in docstatus:
			continue
		for reference in sorted(references):
			if (report, reference) in existing:
				continue
			idx = max_idx.get(report, 0) + 1
			max_idx[report] = idx
			_insert_row(
				report,
				idx,
				docstatus[report],
				{"source": source, "source_type": "External System", "external_id": reference},
			)
			created += 1
	return created


def _write_document_rows(documents):
	"""One row per report and referenced document, as a real Dynamic Link."""
	reports = [d.report for d in documents]
	docstatus = _docstatus_by_report(reports)
	existing, max_idx = _existing_rows(reports)

	created = 0
	for entry in documents:
		if entry.report not in docstatus:
			continue
		if (entry.report, entry.document) in existing:
			continue
		idx = max_idx.get(entry.report, 0) + 1
		max_idx[entry.report] = idx
		_insert_row(
			entry.report,
			idx,
			docstatus[entry.report],
			{
				"source": _ensure_document_source(entry.doctype),
				"source_type": "Document",
				"document_type": entry.doctype,
				"document_name": entry.document,
			},
		)
		created += 1
	return created


def _docstatus_by_report(reports):
	if not reports:
		return {}
	return {
		r.name: r.docstatus
		for r in frappe.get_all(
			"Service Report", filters={"name": ("in", list(set(reports)))}, fields=["name", "docstatus"]
		)
	}


def _existing_rows(reports):
	"""({(report, reference)}, {report: max idx}) for rows already migrated."""
	if not reports:
		return set(), {}

	rows = frappe.get_all(
		"Service Report Reference",
		filters={"parent": ("in", list(set(reports))), "parenttype": "Service Report"},
		fields=["parent", "external_id", "document_name", "idx"],
	)
	existing = {(r.parent, r.document_name or r.external_id) for r in rows}
	max_idx = {}
	for r in rows:
		max_idx[r.parent] = max(max_idx.get(r.parent, 0), r.idx or 0)
	return existing, max_idx


def _insert_row(report, idx, docstatus, values):
	row = frappe.get_doc(
		{
			"doctype": "Service Report Reference",
			"parent": report,
			"parenttype": "Service Report",
			"parentfield": "references",
			"idx": idx,
			**values,
		}
	)
	row.docstatus = docstatus
	row.db_insert()
