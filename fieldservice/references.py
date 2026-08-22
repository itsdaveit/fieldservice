# Copyright (c) 2026, itsdave GmbH and contributors
# For license information, please see license.txt

"""References on Service Reports.

A service report can relate to two kinds of things: documents on this site
(a quotation, an order, an IT object) and records in systems outside it
(a helpdesk ticket, a Jira issue). Both are described by a `Reference Source`
master record and land in one table on the report — documents as a real
Dynamic Link, external records as an ID plus a deep link built from the
source's URL template.

Work positions carry a plain reference of their own, because that is where
the work happens; they are collected into the report's table on every save.
Without any configured source the field is simply free text, so the app
stays usable out of the box.
"""

import re

import frappe
from frappe import _

from fieldservice.fieldservice.doctype.reference_source.reference_source import (
	get_default_reference_source,
)


def sync_references(doc):
	"""Collect references named on work positions into the report's table and
	validate every external reference against its source."""
	default_source = None

	known = set()
	for row in doc.get("references") or []:
		row.external_id = (row.external_id or "").strip()
		known.add(row.document_name or row.external_id)

	for position in doc.get("work") or []:
		reference = (position.reference_id or "").strip()
		position.reference_id = reference
		position.reference_entry = (position.reference_entry or "").strip()
		if not reference or reference in known:
			continue

		if default_source is None:
			default_source = get_default_reference_source() or ""

		row = doc.append("references", {"source": default_source or None})
		_fill_reference(row, reference)
		known.add(reference)

	# Drop rows that lost their reference, renumber the rest
	rows = [r for r in (doc.get("references") or []) if r.document_name or r.external_id]
	for idx, row in enumerate(rows, start=1):
		row.idx = idx
	doc.references = rows

	validate_references(doc)


def _fill_reference(row, reference):
	"""Put the reference into the field its source calls for."""
	source = get_source(row.source)
	row.source_type = (source or {}).get("source_type") or "External System"
	if source and source.get("source_type") == "Document":
		row.document_type = source.get("document_type")
		row.document_name = reference
	else:
		row.external_id = reference


def validate_references(doc):
	"""Check external references against the ID pattern of their source."""
	for row in doc.get("references") or []:
		source = get_source(row.source)
		if not source:
			continue

		# The grid decides by source_type which column to show, so never
		# leave it to fetch_from — rows appended on the server would stay empty.
		row.source_type = source.get("source_type")

		if source.get("source_type") == "Document":
			# The Dynamic Link carries the type; keep it in step with the source.
			row.document_type = source.get("document_type")
			row.external_id = None
			row.external_entry = None
			continue

		row.document_type = None
		row.document_name = None
		pattern = source.get("id_pattern")
		if pattern and row.external_id and not re.match(pattern, row.external_id):
			frappe.throw(
				_("Reference {0} in row {1} does not match the pattern {2} of source {3}.").format(
					frappe.bold(row.external_id), row.idx, frappe.bold(pattern), row.source
				),
				title=_("Invalid Reference"),
			)


def get_source_map():
	"""All enabled reference sources with everything needed to build links."""
	sources = frappe.get_all(
		"Reference Source",
		filters={"enabled": 1},
		fields=[
			"name",
			"title",
			"source_type",
			"document_type",
			"url_template",
			"entry_url_template",
			"id_pattern",
			"is_default",
		],
	)
	return {s["name"]: s for s in sources}


def get_source(name):
	if not name:
		return None
	return get_source_map().get(name)


@frappe.whitelist()
def get_reference_sources():
	"""Enabled sources for the client, so it can render links without a round
	trip per row (unsaved rows included)."""
	return list(get_source_map().values())


def build_urls(source, reference, entry=None):
	"""(url, entry_url) for a reference under the given source dict."""
	if not (source and reference):
		return None, None

	if source.get("source_type") == "Document":
		document_type = source.get("document_type")
		if not document_type:
			return None, None
		route = frappe.scrub(document_type).replace("_", "-")
		return f"/app/{route}/{reference}", None

	url = None
	if source.get("url_template"):
		url = source["url_template"].replace("{id}", str(reference))

	entry_url = None
	if entry and source.get("entry_url_template"):
		entry_url = (
			source["entry_url_template"]
			.replace("{id}", str(reference))
			.replace("{entry}", str(entry))
		)

	return url, entry_url


def get_reference_links(doc):
	"""Resolved links for a Service Report — usable from print formats."""
	sources = get_source_map()
	links = []
	for row in doc.get("references") or []:
		source = sources.get(row.source) or {}
		reference = row.document_name or row.external_id
		url, entry_url = build_urls(source, reference, row.external_entry)
		links.append(
			{
				"source": row.source,
				"source_type": source.get("source_type"),
				"reference": reference,
				"entry": row.external_entry,
				"subject": row.subject,
				"url": url,
				"entry_url": entry_url,
			}
		)
	return links
