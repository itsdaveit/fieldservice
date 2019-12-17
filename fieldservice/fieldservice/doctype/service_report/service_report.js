// Copyright (c) 2019, itsdve GmbH and contributors
// For license information, please see license.txt



frappe.ui.form.on('Service Report', {
	refresh: function(frm) {
        if(frm.doc.docstatus===1) {
            cur_frm.add_custom_button(__("Create Delivery Note"), function() {
                frappe.call({
                    "method": "fieldservice.api.create_delivery_note",
                    args: {
                        "service_report": frm.doc.name,
                        "customer": frm.doc.customer
                        
                    },
                    callback: (response) => {
                        console.log(response.message);
                    } 
                })
            });
        };
        cur_frm.add_custom_button(__("Show Info"), function() {
            frappe.call({
                method: "frappe.client.get_value",
                async:false,
                args:{
                    doctype:'User',
                    filters:{
                        name:frm.doc.owner
                    },
                    fieldname:['full_name']
                },
                callback:function (r) {
                    if(r.message != undefined){
                        console.log(r.message.full_name)
                    };
                    console.log(frappe.user)
                }
            });
        })

    },
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
	customer: function(frm) {
		erpnext.utils.get_party_details(frm);
	},
	customer_address: function(frm) {
		erpnext.utils.get_address_display(frm);
	},
	contact_person: function(frm) {
		erpnext.utils.get_contact_details(frm);
	}
});

frappe.ui.form.on("Service Report Item", {
    item: function(frm, cdt, cdn) {
        var cur_doc = locals[cdt][cdn];
        frappe.call({
            "method": "frappe.client.get",
            args: {
                doctype: "Item",
                name: cur_doc.item
			},
			callback: function (data) {
                frappe.model.set_value(cur_doc.item_name = data.message.item_name);
                //frm.refresh_fields();
			}
		})
        

    }
});

