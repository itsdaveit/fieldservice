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

        frm.add_custom_button(__('Materialbedarf erstellen'), function() {
            if (frm.doc.customer) {
                console.log('Kunde vorhanden, prüfe auf bestehenden Materialbedarf...');
                
                frappe.db.get_value('Materialbedarf', {service_report: frm.doc.name}, 'name')
                    .then(r => {
                        console.log('Abfrageergebnis:', r);
                        
                        if (r.message && r.message.name) {
                            let materialbedarf_name = r.message.name;
                            let materialbedarf_link = frappe.utils.get_form_link('Materialbedarf', materialbedarf_name);
                            let msg_text = `Der Materialbedarf <a href="${materialbedarf_link}">${materialbedarf_name}</a> existiert bereits.`;
                            frappe.msgprint({message: msg_text, title: __('Hinweis'), indicator: 'orange'});
                        } else {
                            console.log('Kein bestehender Materialbedarf gefunden, erstelle neuen...');
                            
                            frappe.new_doc('Materialbedarf', {
                                kunde: frm.doc.customer,
                                service_report: frm.doc.name,
                                project: frm.doc.project
                            });
                        }
                    }).catch(err => {
                        console.error('Fehler bei der Abfrage:', err);
                    });
            } else {
                console.log('Kein Kunde ausgewählt.');
                frappe.msgprint(__('Bitte wählen Sie zuerst einen Kunden aus.'));
            }
        });
        
        
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
                frappe.call({
                    "method": "fieldservice.fieldservice.doctype.service_report.service_report.start_timer",
                    args: {
                        "service_report": frm.doc.name,             
                    },
                    callback: (response) => {
                        frm.reload_doc()
                    } 
                })
    
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
    
    // add_kilometers: function(frm) {
    //     frm.save_or_update({
    //         callback: function() {
    //             frappe.call({
    //                 method: "fieldservice.fieldservice.doctype.service_report.service_report.add_travel",
    //                 args: {
    //                     docname: frm.doc.name
    //                 },
    //                 callback: function(response) {
    //                     frappe.msgprint(__('Anfahrt hinzugefügt'));
    //                     frm.reload_doc();
    //                 }
    //             });
    //         }
    //     });
    // },
    
    // add_kilometers: function(frm) {
    //     console.log(frm.doc.distance)

    //         frappe.call({
    //             method: "fieldservice.fieldservice.doctype.service_report.service_report.add_travel",
    //             args: {
    //                 docname: frm.doc.name
    //             },
    //             callback: function(response) {
    //                 frappe.msgprint(__('Anfahrt hinzugefügt'));
    //                 frm.reload_doc();
    //             }
    //         });
    // },
    add_kilometers: function(frm) {
        console.log(frm.doc.distance);
    
        frappe.call({
            method: "fieldservice.fieldservice.doctype.service_report.service_report.add_travel",
            args: {
                docname: frm.doc.name,
                distance: frm.doc.distance  // Übergebe die Distance hier
            },
            callback: function(response) {
                frappe.msgprint(__('Anfahrt hinzugefügt'));
                frm.reload_doc();
            }
        });
    },
    
    


    "employee": function(frm) {
        
        if (!frm.doc.employee) {
            frappe.call({
                method: "frappe.client.get_value",
                async: false,
                args: {
                    doctype: 'Employee',
                    filters: {
                        user_id: frappe.user.name
                    },
                    fieldname: ['employee_name']
                },
                callback: function(r) {
                    if (r.message !== undefined) {
                        frappe.model.set_value(frm.doctype, frm.docname, "employee_name", r.message.employee_name);
                    }
                }
            });
        }
        if (frm.doc.employee) {
            frappe.call({
                "method": "frappe.client.get_value",
                async: false,
                args: {
                    doctype: "Employee",
                    filters: {
                        name: frm.doc.employee
                    },
                    fieldname: ['employee_name']
                    
                },
                callback: function (data) {
                    frappe.model.set_value(frm.doctype,
                        frm.docname, "employee_name",
                        data.message.employee_name)
                }
            })
        }
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

    project: function(frm) {
        if (frm.doc.project) {
            console.log("Ausgewähltes Projekt:", frm.doc.project); // Debug-Ausgabe
            frappe.db.get_single_value('Fieldservice Settings', 'standard_project')
                .then(standard_project => {
                    if (frm.doc.project !== standard_project) {
                        frappe.db.get_value('Project', frm.doc.project, 'customer', (r) => {
                            console.log("Projektdetails:", r); // Debug-Ausgabe
                            if (r && r.customer) {
                                console.log("Kunde wird gesetzt auf:", r.customer); // Debug-Ausgabe
                                frm.set_value('customer', r.customer).then(() => {
                                    frm.trigger('customer');
                                });
                            }
                        });
                    } else {
                        if (!frm.is_standard_project_notified) {
                            console.log("Das ausgewählte Projekt ist das Standardprojekt. Kein Kunde wird gesetzt.");
                            frappe.msgprint(__("Das ausgewählte Projekt ist das Standardprojekt. Kein Kunde wurde gesetzt."));
                            frm.is_standard_project_notified = true;
                        }
                    }
                });
        } else {
            frm.is_standard_project_notified = false;
        }
    }
    
    // project: function(frm) {
    //     if (frm.doc.project) {
    //         console.log("Ausgewähltes Projekt:", frm.doc.project); // Debug-Ausgabe
    //         // Standardprojekt aus den Fieldservice Settings abrufen
    //         frappe.db.get_single_value('Fieldservice Settings', 'standard_project')
    //             .then(standard_project => {
    //                 if (frm.doc.project !== standard_project) {
    //                     // Fortfahren, wenn das ausgewählte Projekt nicht das Standardprojekt ist
    //                     frappe.db.get_value('Project', frm.doc.project, 'customer', (r) => {
    //                         console.log("Projektdetails:", r); // Debug-Ausgabe
    //                         if (r && r.customer) {
    //                             console.log("Kunde wird gesetzt auf:", r.customer); // Debug-Ausgabe
    //                             frm.set_value('customer', r.customer).then(() => {
    //                                 frm.trigger('customer'); // Kundenfunktion auslösen, nachdem das Kundenfeld gesetzt wurde
    //                             });
    //                         }
    //                     });
    //                 } else {
    //                     console.log("Das ausgewählte Projekt ist das Standardprojekt. Kein Kunde wird gesetzt.");
    //                     frappe.msgprint(__("Das ausgewählte Projekt ist das Standardprojekt. Kein Kunde wird gesetzt."));
    //                 }
    //             });
    //     }
    // }
    
    // project: function(frm) {
    //     if (frm.doc.project) { // Make sure the field name is correct
    //         console.log("Selected project:", frm.doc.project); // Debugging output
    //         frappe.db.get_value('Project', frm.doc.project, 'customer', (r) => {
    //             console.log("Project details:", r); // Debugging output
    //             if (r && r.customer) {
    //                 console.log("Setting customer to:", r.customer); // Debugging output
    //                 frm.set_value('customer', r.customer).then(() => {
    //                     frm.trigger('customer'); // Trigger the customer function to execute after setting the customer field
    //                 });
    //             }
    //         });
    //     }
    // }
    
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
            service_type = frm.doc.report_type,
            index = frappe.model.get_value(cdt,cdn,"idx");
        console.log(service_type);   
        console.log("Work Item hinzugefügt");
         
        frappe.model.set_value(cdt,cdn,"service_type",service_type);
        frappe.model.set_value (cdt,cdn,"address" , address);
        if (service_type === "On-Site Service" && index ===1){
            frappe.model.set_value(cdt,cdn,"travel_charges",1);
		

        }

        cur_frm.refresh_field("work");
    }
});

