import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CHILD_DOCTYPE = "Service Report Connected Checklist"


def sync_checklist_field():
	"""Add the `checklists` table field to Service Report only when its child
	DocType (provided by the `msp` app) is installed. On sites without `msp`
	the field is removed so the Service Report form can load (a Table field
	pointing at a missing DocType breaks get_meta_bundle on form load)."""
	child_exists = bool(frappe.db.exists("DocType", CHILD_DOCTYPE))
	field_exists = bool(frappe.db.exists("Custom Field", "Service Report-checklists"))

	if child_exists and not field_exists:
		create_custom_fields(
			{
				"Service Report": [
					{
						"fieldname": "checklists_section",
						"fieldtype": "Section Break",
						"label": "Checklists",
						"insert_after": "items",
					},
					{
						"fieldname": "checklists",
						"fieldtype": "Table",
						"label": "Checklists",
						"options": CHILD_DOCTYPE,
						"insert_after": "checklists_section",
					},
				]
			}
		)
	elif not child_exists and field_exists:
		for fn in ("Service Report-checklists", "Service Report-checklists_section"):
			if frappe.db.exists("Custom Field", fn):
				frappe.delete_doc("Custom Field", fn, force=1, ignore_permissions=True)


DEFAULT_DOCUMENT_SOURCES = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"]


def seed_reference_sources():
	"""Create a document reference source per standard sales document, so a
	fresh site can reference its own documents right away.

	Called once on install and once from the reference migration patch —
	never from after_migrate, which would resurrect sources a tenant
	deliberately deleted."""
	for doctype in DEFAULT_DOCUMENT_SOURCES:
		if not frappe.db.exists("DocType", doctype):
			continue
		if frappe.db.exists("Reference Source", {"source_type": "Document", "document_type": doctype}):
			continue
		if frappe.db.exists("Reference Source", _doctype_label(doctype)):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Reference Source",
				"title": _doctype_label(doctype),
				"source_type": "Document",
				"document_type": doctype,
				"enabled": 1,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()


def _doctype_label(doctype):
	"""Translated DocType name, so the source reads naturally per language."""
	return frappe._(doctype)
