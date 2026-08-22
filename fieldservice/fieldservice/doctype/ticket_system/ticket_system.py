# Copyright (c) 2026, itsdave GmbH and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class TicketSystem(Document):
	def validate(self):
		self.validate_pattern()
		self.validate_templates()

	def validate_pattern(self):
		if not self.id_pattern:
			return
		try:
			re.compile(self.id_pattern)
		except re.error as e:
			frappe.throw(_("ID Pattern is not a valid regular expression: {0}").format(e))

	def validate_templates(self):
		if self.ticket_url_template and "{id}" not in self.ticket_url_template:
			frappe.throw(_("Ticket URL Template must contain the placeholder {0}").format("{id}"))
		if self.entry_url_template and "{entry}" not in self.entry_url_template:
			frappe.throw(_("Entry URL Template must contain the placeholder {0}").format("{entry}"))

	def on_update(self):
		if self.is_default:
			frappe.db.set_value(
				"Ticket System",
				{"name": ("!=", self.name), "is_default": 1},
				"is_default",
				0,
				update_modified=False,
			)

	def build_ticket_url(self, ticket_reference):
		if not ticket_reference:
			return None
		if self.local_doctype and frappe.db.exists("DocType", self.local_doctype):
			return f"/app/{frappe.scrub(self.local_doctype).replace('_', '-')}/{ticket_reference}"
		if self.ticket_url_template:
			return self.ticket_url_template.replace("{id}", str(ticket_reference))
		return None

	def build_entry_url(self, ticket_reference, entry):
		if not (entry and self.entry_url_template):
			return None
		return self.entry_url_template.replace("{id}", str(ticket_reference or "")).replace(
			"{entry}", str(entry)
		)


def get_default_ticket_system():
	"""Name of the default ticket system, or the only enabled one."""
	default = frappe.db.get_value("Ticket System", {"is_default": 1, "enabled": 1}, "name")
	if default:
		return default
	enabled = frappe.get_all("Ticket System", filters={"enabled": 1}, pluck="name", limit=2)
	return enabled[0] if len(enabled) == 1 else None
