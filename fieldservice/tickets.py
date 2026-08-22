# Copyright (c) 2026, itsdave GmbH and contributors
# For license information, please see license.txt

"""Ticket references on Service Reports.

A service report carries a table of ticket references (`ticket_references`);
each work position can name the ticket it was worked on. Positions are the
place where the work happens, the table is the collected view over the whole
report — kept in sync on every save.

The ticket system itself is a plain master record (`Ticket System`), so the
app stays tenant neutral: without any configuration the reference is a free
text field, with a configured system it becomes a deep link, and if the
ticket system happens to live on this very site it links the document.
"""

import re

import frappe
from frappe import _

from fieldservice.fieldservice.doctype.ticket_system.ticket_system import (
	get_default_ticket_system,
)


def sync_ticket_references(doc):
	"""Collect tickets named on work positions into the report's table and
	validate every reference against its ticket system."""
	default_system = None

	by_reference = {}
	for row in doc.get("ticket_references") or []:
		row.ticket_reference = (row.ticket_reference or "").strip()
		if not row.ticket_reference:
			continue
		by_reference.setdefault(row.ticket_reference, row)

	for position in doc.get("work") or []:
		reference = (position.ticket_reference or "").strip()
		position.ticket_reference = reference
		position.ticket_entry = (position.ticket_entry or "").strip()
		if not reference or reference in by_reference:
			continue

		if default_system is None:
			default_system = get_default_ticket_system() or ""

		by_reference[reference] = doc.append(
			"ticket_references",
			{"ticket_system": default_system or None, "ticket_reference": reference},
		)

	# Drop rows that lost their reference, renumber the rest
	rows = [r for r in (doc.get("ticket_references") or []) if r.ticket_reference]
	for idx, row in enumerate(rows, start=1):
		row.idx = idx
	doc.ticket_references = rows

	validate_ticket_references(doc)


def validate_ticket_references(doc):
	"""Check references against the ID pattern of their ticket system."""
	patterns = {}
	for row in doc.get("ticket_references") or []:
		if not row.ticket_system:
			continue
		if row.ticket_system not in patterns:
			patterns[row.ticket_system] = frappe.db.get_value(
				"Ticket System", row.ticket_system, "id_pattern"
			)
		pattern = patterns[row.ticket_system]
		if pattern and not re.match(pattern, row.ticket_reference):
			frappe.throw(
				_("Ticket reference {0} in row {1} does not match the pattern {2} of ticket system {3}.").format(
					frappe.bold(row.ticket_reference), row.idx, frappe.bold(pattern), row.ticket_system
				),
				title=_("Invalid Ticket Reference"),
			)


def get_ticket_system_map():
	"""All enabled ticket systems with everything needed to build links."""
	systems = frappe.get_all(
		"Ticket System",
		filters={"enabled": 1},
		fields=[
			"name",
			"title",
			"ticket_url_template",
			"entry_url_template",
			"local_doctype",
			"is_default",
		],
	)
	return {s["name"]: s for s in systems}


@frappe.whitelist()
def get_ticket_systems():
	"""Enabled ticket systems for the client, so it can render links without
	a round trip per row (unsaved rows included)."""
	return list(get_ticket_system_map().values())


def build_urls(system, ticket_reference, ticket_entry=None):
	"""(ticket_url, entry_url) for a reference under the given system dict."""
	if not (system and ticket_reference):
		return None, None

	ticket_url = None
	local_doctype = system.get("local_doctype")
	if local_doctype and frappe.db.exists("DocType", local_doctype):
		route = frappe.scrub(local_doctype).replace("_", "-")
		ticket_url = f"/app/{route}/{ticket_reference}"
	elif system.get("ticket_url_template"):
		ticket_url = system["ticket_url_template"].replace("{id}", str(ticket_reference))

	entry_url = None
	if ticket_entry and system.get("entry_url_template"):
		entry_url = (
			system["entry_url_template"]
			.replace("{id}", str(ticket_reference))
			.replace("{entry}", str(ticket_entry))
		)

	return ticket_url, entry_url


def get_ticket_links(doc):
	"""Resolved links for a Service Report — usable from print formats."""
	systems = get_ticket_system_map()
	links = []
	for row in doc.get("ticket_references") or []:
		system = systems.get(row.ticket_system) or {}
		ticket_url, entry_url = build_urls(system, row.ticket_reference, row.ticket_entry)
		links.append(
			{
				"ticket_system": row.ticket_system,
				"ticket_reference": row.ticket_reference,
				"ticket_entry": row.ticket_entry,
				"subject": row.subject,
				"url": ticket_url,
				"entry_url": entry_url,
			}
		)
	return links
