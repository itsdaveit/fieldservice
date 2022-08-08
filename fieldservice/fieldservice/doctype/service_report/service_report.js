// Copyright (c) 2019, itsdve GmbH and contributors
// For license information, please see license.txt



frappe.ui.form.on('Service Report', {
    setup: function(frm) {
		frm.set_query("customer", function() {
			return {
				"filters": {
					"disabled":  0
                }
			}
		});
	},


    scan_barcode: function(frm) {
        let transaction_controller= new erpnext.TransactionController({frm});
        transaction_controller.scan_barcode();
    },


	refresh: function(frm) {
        console.log(frm.doc.status)
        console.log(frm.doc.docstatus)

        if(frm.doc.docstatus===1) {
            cur_frm.add_custom_button(__("Create Delivery Note"), function() {
                frappe.call({
                    "method": "fieldservice.api.create_delivery_note",
                    args: {
                        "service_report": frm.doc.name,
                        "customer": frm.doc.customer
                        
                    },
                    callback: (response) => {
                        console.log(response.message),
                        frm.reload_doc();
                    } 
                })
            });
        };
        

        if(frm.doc.status=="Draft" & !frm.is_new()) {
            clearInterval();
            cur_frm.add_custom_button(__("Start Timer"), function() {
                frm.set_value("status", "Started")
                frm.set_value("timer_start", frappe.datetime.now_datetime())
                frm.save()
            });
            frm.change_custom_button_type("Start Timer", null, "success");
            
        };

        if(frm.doc.status=="Started" & !frm.is_new()) {
            let myInterval = setInterval(function() {
                let currentdt = new Date()
                let startdt = new Date(Date.parse(frm.doc.timer_start))
                let diff = currentdt - startdt
                document.getElementById("timer").innerHTML = currentdt + "<br>" + startdt + "<br>" + diff;
            }, 1000);
            cur_frm.add_custom_button(__("Stop Timer"), function() {
                clearInterval(myInterval);
                frappe.call({
                    "method": "fieldservice.fieldservice.doctype.service_report.service_report.stop_timer",
                    args: {
                        "service_report": frm.doc.name,                        
                    },
                    callback: (response) => {
                        console.log(response.message),
                        frm.reload_doc()
                    } 
                })
            });
            frm.change_custom_button_type("Stop Timer", null, "danger");
            frm.disable_save();
        };
        
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
	},
});


frappe.ui.form.on("Service Report Item", {
    item_code: function(frm, cdt, cdn) {
        var cur_doc = locals[cdt][cdn];
        frappe.call({
            "method": "frappe.client.get",
            args: {
                doctype: "Item",
                name: cur_doc.item_code
			},
			callback: function (data) {
                frappe.model.set_value(cur_doc.item_name = data.message.item_name);
                frm.refresh_fields();
			}
		})
        

    }
});