// Copyright (c) 2019, itsdve GmbH and contributors
// For license information, please see license.txt

let sr_report_Interval;

function padTo2Digits(num) {
    return num.toString().padStart(2, '0');
  }
  

function convertMsToTime(milliseconds) {
    let seconds = Math.floor(milliseconds / 1000);
    let minutes = Math.floor(seconds / 60);
    let hours = Math.floor(minutes / 60);
  
    seconds = seconds % 60;
    minutes = minutes % 60;
  
    // 👇️ If you don't want to roll hours over, e.g. 24 to 00
    // 👇️ comment (or remove) the line below
    // commenting next line gets you `24:00:00` instead of `00:00:00`
    // or `36:15:31` instead of `12:15:31`, etc.
    hours = hours % 24;
  
    return `${padTo2Digits(hours)}:${padTo2Digits(minutes)}:${padTo2Digits(
      seconds,
    )}`;
  }
  

function format_timer(duration) {
    return "<h1 class='display-4' style='margin-bottom: 0px;'>" + duration + "</h1>"
}


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

    onload: function(frm){
        frm.trigger('employee')
        frm.trigger('customer')
        
    },
	refresh: function(frm) {

        if (sr_report_Interval != frm.doc.current_sr_report_Interval) {
            clearInterval(sr_report_Interval);
        }

        if(frm.doc.docstatus===1) {
            cur_frm.add_custom_button(__("Create Delivery Note"), function() {
                frappe.call({
                    "method": "fieldservice.api.insert_surchargs_in_delivery_note",
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
            let current_sr_report_Interval = setInterval(function() {
                let currentdt = new Date()
                let startdt = new Date(Date.parse(frm.doc.timer_start))
                let diff = currentdt - startdt
                let duration = convertMsToTime(diff)
                document.getElementById("timer").innerHTML = format_timer(duration);
            }, 1000);
            sr_report_Interval = current_sr_report_Interval
            cur_frm.add_custom_button(__("Stop Timer"), function() {
                let d = new frappe.ui.Dialog({
                    title: 'Enter details',
                    fields: [
                        {
                            label: 'Description for Work',
                            fieldname: 'description',
                            fieldtype: 'Text Editor'
                        }
                    ],
                    primary_action_label: 'Submit',
                    primary_action(values) {
                        frappe.call({
                            "method": "fieldservice.fieldservice.doctype.service_report.service_report.stop_timer",
                            args: {
                                "service_report": frm.doc.name,
                                "description": values.description               
                            },
                            callback: (response) => {
                                clearInterval(sr_report_Interval),
                                d.hide(),
                                console.log(response.message),
                                frm.reload_doc()
                            } 
                        })
                    }
                });
                d.show()
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
frappe.ui.form.on('Service Report Work',{ 
    work_add(frm, cdt, cdn) {
        let address = frm.doc.customer_address,
            service_type = frm.doc.report_type
            index = frappe.model.get_value(cdt,cdn,"idx")
        console.log(service_type)   
        console.log("Work Item hinzugefügt")
         
        frappe.model.set_value(cdt,cdn,"service_type",service_type)
        frappe.model.set_value (cdt,cdn,"address" , address)
        if (service_type === "On-Site Service" && index ===1){
            frappe.model.set_value(cdt,cdn,"travel_charges",1)   

        }

        cur_frm.refresh_field("work");
    }
});

