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


DEFAULT_REFERENCE_DOCTYPES = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"]


def seed_reference_document_types():
	"""Pre-fill Fieldservice Settings with the default reference DocTypes
	(Quotation / Sales Order / Delivery Note / Sales Invoice) when the list
	is empty, so the defaults are visible and editable."""
	settings = frappe.get_single("Fieldservice Settings")
	if settings.get("reference_document_types"):
		return
	for dt in DEFAULT_REFERENCE_DOCTYPES:
		if frappe.db.exists("DocType", dt):
			settings.append("reference_document_types", {"document_type": dt})
	settings.flags.ignore_permissions = True
	settings.save()
