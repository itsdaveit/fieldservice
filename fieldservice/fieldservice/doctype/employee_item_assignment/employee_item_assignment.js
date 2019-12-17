// Copyright (c) 2019, itsdve GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Employee Item Assignment', {
	// refresh: function(frm) {

	// }
	"employee" : function(frm) {
        frappe.call({
            "method": "frappe.client.get",
            args: {
                doctype: "Employee",
                name: frm.doc.employee
			},
			callback: function (data) {
                frappe.model.set_value(frm.doctype,
                    frm.docname, "employee_name",
                    data.message.employee_name)
			}
		})
	},
	"item" : function(frm) {
        frappe.call({
            "method": "frappe.client.get",
            args: {
                doctype: "Item",
                name: frm.doc.item
			},
			callback: function (data) {
                frappe.model.set_value(frm.doctype,
                    frm.docname, "item_name",
                    data.message.item_name)
			}
		})
	},
});
