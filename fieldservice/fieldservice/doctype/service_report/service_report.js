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


function set_link_filters(frm) {
    // Contact filter
    if (frm.doc.filter_contact_by_customer && frm.doc.customer) {
        frm.set_query("contact_person", function() {
            return {
                query: "frappe.contacts.doctype.contact.contact.contact_query",
                filters: { link_doctype: "Customer", link_name: frm.doc.customer }
            };
        });
    } else {
        frm.set_query("contact_person", function() { return {}; });
    }

    // Address filter
    if (frm.doc.filter_address_by_customer && frm.doc.customer) {
        frm.set_query("customer_address", function() {
            return {
                query: "frappe.contacts.doctype.address.address.address_query",
                filters: { link_doctype: "Customer", link_name: frm.doc.customer }
            };
        });
    } else {
        frm.set_query("customer_address", function() { return {}; });
    }
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
        set_link_filters(frm);

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
       
        frappe.call({
            method: "frappe.client.get_value",
            args: {
                doctype: "OTRSConnect User Settings",
                fieldname: ["zoom_link"]
            },
            callback(r) {
                if(r.message && frm.doc.ofork_ticket_number) {
                    console.log(r.message);
                    frm.add_custom_button(__('OTRS Ticket Zoom'), function() {
                        window.open(r.message["zoom_link"] + frm.doc.ofork_ticket_number, '_blank');
                    }, __("Ofork Ticket"));
                }
            }
        });

        // Button to set selected rows to "Without Surcharge"
        frm.add_custom_button(__('selektierte ohne Zuschlag'), function() {
            let selected_rows = frm.fields_dict.work.grid.get_selected_children();

            if (selected_rows.length === 0) {
                frappe.msgprint(__('Bitte wählen Sie mindestens eine Zeile aus.'));
                return;
            }

            selected_rows.forEach(function(row) {
                frappe.model.set_value(row.doctype, row.name, 'ignore_surcharges', 1);
            });

            frm.refresh_field('work');
            frappe.show_alert({
                message: __('Zuschlag für {0} Zeile(n) deaktiviert', [selected_rows.length]),
                indicator: 'green'
            });
        }, __("Funktionen"));

        // Button to set selected rows to "With Surcharge"
        frm.add_custom_button(__('selektierte mit Zuschlag'), function() {
            let selected_rows = frm.fields_dict.work.grid.get_selected_children();

            if (selected_rows.length === 0) {
                frappe.msgprint(__('Bitte wählen Sie mindestens eine Zeile aus.'));
                return;
            }

            selected_rows.forEach(function(row) {
                frappe.model.set_value(row.doctype, row.name, 'ignore_surcharges', 0);
            });

            frm.refresh_field('work');
            frappe.show_alert({
                message: __('Zuschlag für {0} Zeile(n) aktiviert', [selected_rows.length]),
                indicator: 'green'
            });
        }, __("Funktionen"));

        // Review Pipeline button (only in Draft)
        if (frm.doc.status === "Draft" && !frm.is_new()) {
            frm.add_custom_button(__('Beschreibungen pruefen'), function() {
                frappe.call({
                    method: 'fieldservice.fieldservice.doctype.service_report.service_report.run_review',
                    args: { service_report: frm.doc.name },
                    callback: function(r) {
                        if (!r.message || r.message.length === 0) return;
                        show_review_dialog(frm, JSON.stringify(r.message));
                    }
                });
            }, __("Funktionen"));
        }
        
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
    




	// "employee" : function(frm) {
    //     if (frm.doc.employee) {
    //     frappe.call({
    //         "method": "frappe.client.get",
    //         args: {
    //             doctype: "Employee",
    //             name: frm.doc.employee
	// 		},
	// 		callback: function (data) {
    //             frappe.model.set_value(frm.doctype,
    //                 frm.docname, "employee_name",
    //                 data.message.employee_name)
	// 		}
	// 	})
	// }
    //     if (not frm.doc.employee)
    //     {frappe.call({
    //         method: "frappe.client.get_value",
    //         async:false,
    //         args:{
    //             doctype:'Employee',
    //             filters:{
    //                 user_id:frappe.user.name
    //             },
    //             fieldname:['name']
    //         },
    //         callback:function (r) {
    //             if(r.message != undefined){
    //                 frappe.model.set_value(frm.doctype,
    //                     frm.docname, "employee_name",
    //                     r.message.name)

    //                 };
    //                 console.log(r.message.name)
    //             };
                
    //         }
    //     },

	customer: function(frm) {
		erpnext.utils.get_party_details(frm);
		set_link_filters(frm);
	},
	filter_contact_by_customer: function(frm) {
		set_link_filters(frm);
	},
	filter_address_by_customer: function(frm) {
		set_link_filters(frm);
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


// ---------------------------------------------------------------------------
// Review Pipeline: Confirm Dialog
// ---------------------------------------------------------------------------

function show_review_dialog(frm, fixes_data, from_submit) {
    let fixes;
    try {
        if (typeof fixes_data === 'string') {
            fixes = JSON.parse(fixes_data);
        } else {
            fixes = fixes_data;
        }
    } catch(e) {
        frappe.msgprint(__('Error parsing review data'));
        return;
    }

    // Quill bullet list CSS for dialog preview
    let style = '<style>'
        + '.review-results ol { list-style: none; padding-left: 1.5em; margin: 0; }'
        + '.review-results li { list-style-type: none; padding-left: 1.5em; position: relative; }'
        + '.review-results li[data-list="bullet"] > .ql-ui { display: none; }'
        + '.review-results li[data-list="bullet"]::before { content: "\\2022"; position: absolute; left: 0; }'
        + '.review-preview { padding: 8px 12px; border-radius: 4px; margin-bottom: 8px; max-height: 300px; overflow-y: auto; }'
        + '.review-preview-before { background: var(--bg-light-gray, #f5f5f5); }'
        + '.review-preview-after { background: #e8f5e9; }'
        + '</style>';

    let body = style + '<div class="review-results">';
    fixes.forEach(function(fix) {
        let field_match = fix.field.match(/work\[(\d+)\]/);
        let pos_label = field_match ? 'Position ' + (parseInt(field_match[1]) + 1) : fix.field;

        body += '<div class="review-item" style="margin-bottom: 15px; padding: 10px; border: 1px solid var(--border-color); border-radius: 4px;">';
        body += '<strong>' + pos_label + '</strong> &mdash; ' + fix.message + '<br>';
        body += '<div style="margin-top: 8px;">';
        body += '<div style="margin-bottom: 5px;"><span class="text-muted">Vorher:</span></div>';
        body += '<div class="review-preview review-preview-before">' + fix.original_value + '</div>';
        body += '<div style="margin-bottom: 5px;"><span class="text-muted">Nachher:</span></div>';
        body += '<div class="review-preview review-preview-after">' + fix.suggested_value + '</div>';
        body += '</div></div>';
    });
    body += '</div>';

    let primary_label = from_submit ? __('Uebernehmen & Buchen') : __('Uebernehmen');
    let secondary_label = from_submit ? __('Ohne Korrektur buchen') : __('Abbrechen');

    let d = new frappe.ui.Dialog({
        title: __('Beschreibungen pruefen'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'review_content',
                options: body
            }
        ],
        primary_action_label: primary_label,
        primary_action: function() {
            d.hide();
            if (from_submit) {
                // Apply locally, save, then re-submit
                fixes.forEach(function(fix) {
                    let field_match = fix.field.match(/work\[(\d+)\]\.description/);
                    if (field_match) {
                        let idx = parseInt(field_match[1]);
                        if (idx < frm.doc.work.length) {
                            frm.doc.work[idx].description = fix.suggested_value;
                        }
                    }
                });
                frm.refresh_field('work');
                frm.save().then(() => {
                    frm.call('submit', { flags: { skip_review: true } }).then(() => {
                        frm.reload_doc();
                    });
                });
            } else {
                // Button context: apply via server API and reload
                frappe.call({
                    method: 'fieldservice.fieldservice.doctype.service_report.service_report.apply_review',
                    args: {
                        service_report: frm.doc.name,
                        fixes: JSON.stringify(fixes)
                    },
                    callback: function() {
                        frm.reload_doc();
                    }
                });
            }
        },
        secondary_action_label: secondary_label,
        secondary_action: function() {
            d.hide();
            if (from_submit) {
                // Submit without corrections
                frm.call('submit', { flags: { skip_review: true } }).then(() => {
                    frm.reload_doc();
                });
            }
        }
    });
    d.show();
}

// Hook into frappe submit to intercept review_required errors
const _original_submit = frappe.ui.form.Form.prototype.submit;
if (!frappe.ui.form.Form.prototype._review_submit_patched) {
    frappe.ui.form.Form.prototype._review_submit_patched = true;
    frappe.ui.form.Form.prototype.submit = function() {
        const frm = this;
        if (frm.doctype !== 'Service Report') {
            return _original_submit.apply(this, arguments);
        }
        
        return new Promise((resolve, reject) => {
            _original_submit.apply(this, arguments)
                .then(resolve)
                .catch(function(err) {
                    if (err && err._server_messages) {
                        try {
                            let messages = JSON.parse(err._server_messages);
                            for (let msg of messages) {
                                let parsed = JSON.parse(msg);
                                if (parsed.title === 'review_required') {
                                    show_review_dialog(frm, parsed.message, true);
                                    resolve();
                                    return;
                                }
                            }
                        } catch(e) {}
                    }
                    reject(err);
                });
        });
    };
}
