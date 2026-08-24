# Copyright (c) 2026, itsdave GmbH and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class ReferenceSource(Document):
	def validate(self):
		self.validate_pattern()
		self.validate_templates()
		self.validate_document_type()

	def validate_pattern(self):
		if not self.id_pattern:
			return
		try:
			re.compile(self.id_pattern)
		except re.error as e:
			frappe.throw(_("ID Pattern is not a valid regular expression: {0}").format(e))

	def validate_templates(self):
		if self.url_template and "{id}" not in self.url_template:
			frappe.throw(_("URL Template must contain the placeholder {0}").format("{id}"))
		if self.entry_url_template and "{entry}" not in self.entry_url_template:
			frappe.throw(_("Entry URL Template must contain the placeholder {0}").format("{entry}"))

	def validate_document_type(self):
		"""Keep the two source types apart: a document source needs a DocType,
		an external one has no business carrying a local link."""
		if self.source_type == "Document":
			if not self.document_type:
				frappe.throw(_("A document source needs a Document Type."))
			self.url_template = None
			self.entry_url_template = None
		else:
			self.document_type = None

	def on_update(self):
		if self.is_default:
			frappe.db.set_value(
				"Reference Source",
				{"name": ("!=", self.name), "is_default": 1},
				"is_default",
				0,
				update_modified=False,
			)


def get_default_reference_source(source_type=None):
	"""Name of the default reference source, or the only enabled one.

	Pass source_type to stay within one kind — work positions carry plain
	text, so they must never be filed under a document source, which would
	turn the text into a Dynamic Link pointing at a document that does not
	exist."""
	filters = {"enabled": 1}
	if source_type:
		filters["source_type"] = source_type

	default = frappe.db.get_value("Reference Source", dict(filters, is_default=1), "name")
	if default:
		return default

	enabled = frappe.get_all("Reference Source", filters=filters, pluck="name", limit=2)
	return enabled[0] if len(enabled) == 1 else None
