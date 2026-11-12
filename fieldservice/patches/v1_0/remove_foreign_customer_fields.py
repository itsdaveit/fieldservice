# Copyright (c) 2026, itsdave GmbH and contributors
# For license information, please see license.txt

import frappe

DATA_FIELDS = (
	"quotation_contact",
	"sales_order_contact",
	"delivery_note_contact",
	"sales_invoice_contact",
	"quotation_contact_email",
	"notes",
	"hornet_domain",
	"billing_mode",
)
CONTACT_LAYOUT_FIELDS = ("itsdave_customer_details", "column_break_29")
CONTACT_FIELDS = DATA_FIELDS[:5]


def execute():
	if "itsdave_inside" in frappe.get_installed_apps():
		return

	columns = set(frappe.db.get_table_columns("Customer"))
	for fieldname in DATA_FIELDS:
		field = _custom_field(fieldname)
		if field and not (fieldname in columns and _holds_values(fieldname, field.default)):
			frappe.delete_doc("Custom Field", field.name, ignore_permissions=True, force=True)

	if not any(_custom_field(fieldname) for fieldname in CONTACT_FIELDS):
		for fieldname in CONTACT_LAYOUT_FIELDS:
			field = _custom_field(fieldname)
			if field:
				frappe.delete_doc("Custom Field", field.name, ignore_permissions=True, force=True)


def _custom_field(fieldname):
	return frappe.db.get_value(
		"Custom Field", {"dt": "Customer", "fieldname": fieldname}, ["name", "default"], as_dict=True
	)


def _holds_values(fieldname, default):
	return bool(
		frappe.db.sql(
			f"""select 1 from `tabCustomer`
			where ifnull(`{fieldname}`, '') != '' and ifnull(`{fieldname}`, '') != %s
			limit 1""",
			default or "",
		)
	)
