# Copyright (c) 2026, itsdave GmbH and contributors
# For license information, please see license.txt

"""Move the legacy OTRS/Ofork ticket columns onto the generic ticket reference model.

`ofork_ticket_number` (Service Report) and `otrs_ticket` / `otrs_article`
(Service Report Work) were removed from the DocTypes when the app was made
tenant neutral. Frappe does not drop database columns on migrate, so the data
is still there — orphaned. This patch reads it straight from the columns and
writes it into `ticket_reference` / `ticket_entry` on the positions and into
the report's `ticket_references` table.

The legacy columns are deliberately left in place: they are the only backup
of this data until the migration has been reviewed on the live system, and
`msp` still reads `otrs_article` in one report query. Dropping them is a
separate, later step.
"""

import frappe

LEGACY_SYSTEM = "OTRS (Alt)"


def execute():
	columns = {
		"sr_ofork": _has_column("Service Report", "ofork_ticket_number"),
		"work_ticket": _has_column("Service Report Work", "otrs_ticket"),
		"work_article": _has_column("Service Report Work", "otrs_article"),
	}
	if not any(columns.values()):
		return

	positions = _legacy_positions(columns)
	reports = _legacy_reports(columns)
	if not (positions or reports):
		return

	system = _ensure_legacy_system()

	migrated_positions = _migrate_positions(positions)
	migrated_rows = _migrate_report_tables(reports, positions, system)

	frappe.db.commit()
	print(
		f"fieldservice: migrated {migrated_positions} legacy ticket positions "
		f"and created {migrated_rows} ticket reference rows"
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
		f"({col} IS NOT NULL AND {col} != '')"
		for col in (ticket, article)
		if col != "NULL"
	)

	return frappe.db.sql(
		f"""
		SELECT name, parent, {ticket} AS ticket, {article} AS entry
		FROM `tabService Report Work`
		WHERE {where}
		""",
		as_dict=True,
	)


def _legacy_reports(columns):
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


def _ensure_legacy_system():
	if frappe.db.exists("Ticket System", LEGACY_SYSTEM):
		return LEGACY_SYSTEM

	doc = frappe.get_doc(
		{
			"doctype": "Ticket System",
			"title": LEGACY_SYSTEM,
			"enabled": 0,
			"is_default": 0,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _migrate_positions(positions):
	"""Write legacy ticket/article onto the position's own fields."""
	count = 0
	for row in positions:
		values = {}
		if (row.ticket or "").strip():
			values["ticket_reference"] = row.ticket.strip()
		if (row.entry or "").strip():
			values["ticket_entry"] = row.entry.strip()
		if not values:
			continue
		frappe.db.set_value(
			"Service Report Work", row.name, values, update_modified=False
		)
		count += 1
	return count


def _migrate_report_tables(reports, positions, system):
	"""One ticket reference row per report and distinct ticket."""
	# The table lists the tickets a report touched; the entry (article) stays
	# on the position it belongs to, where it is unambiguous.
	wanted = {}
	for report, ticket in reports.items():
		wanted.setdefault(report, set()).add(ticket)

	for row in positions:
		ticket = (row.ticket or "").strip()
		if ticket:
			wanted.setdefault(row.parent, set()).add(ticket)

	if not wanted:
		return 0

	docstatus_by_report = {
		r.name: r.docstatus
		for r in frappe.get_all(
			"Service Report",
			filters={"name": ("in", list(wanted))},
			fields=["name", "docstatus"],
		)
	}

	existing = frappe.get_all(
		"Service Report Ticket Reference",
		filters={"parent": ("in", list(wanted)), "parenttype": "Service Report"},
		fields=["parent", "ticket_reference", "idx"],
	)
	already = {(e.parent, e.ticket_reference) for e in existing}

	max_idx = {}
	for e in existing:
		max_idx[e.parent] = max(max_idx.get(e.parent, 0), e.idx or 0)

	created = 0
	for report, tickets in wanted.items():
		if report not in docstatus_by_report:
			continue
		for ticket in sorted(tickets):
			if (report, ticket) in already:
				continue
			idx = max_idx.get(report, 0) + 1
			max_idx[report] = idx
			row = frappe.get_doc(
				{
					"doctype": "Service Report Ticket Reference",
					"parent": report,
					"parenttype": "Service Report",
					"parentfield": "ticket_references",
					"idx": idx,
					"ticket_system": system,
					"ticket_reference": ticket,
				}
			)
			row.docstatus = docstatus_by_report[report]
			row.db_insert()
			created += 1

	return created
