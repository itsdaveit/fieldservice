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
        render_address_card(frm);
        render_contact_card(frm);
        render_quick_add_buttons(frm);

        if (sr_report_Interval != frm.doc.current_sr_report_Interval) {
            clearInterval(sr_report_Interval);
        }

        if(frm.doc.docstatus===1) {
            cur_frm.add_custom_button(__("📋 Create Delivery Note"), function() {
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

        // Button to set selected rows to "Without Surcharge"
        frm.add_custom_button(__('🚫 Selektierte ohne Zuschlag'), function() {
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
        }, __("Aktionen"));

        // Button to set selected rows to "With Surcharge"
        frm.add_custom_button(__('💰 Selektierte mit Zuschlag'), function() {
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
        }, __("Aktionen"));

        // Button to change service_type for selected rows
        frm.add_custom_button(__('🔧 Servicetyp ändern'), function() {
            let selected_rows = frm.fields_dict.work.grid.get_selected_children();
            if (selected_rows.length === 0) {
                frappe.msgprint(__('Bitte wählen Sie mindestens eine Zeile aus.'));
                return;
            }
            show_change_service_type_dialog(frm, selected_rows);
        }, __("Aktionen"));

        // Review Pipeline button (only in Draft)
        if (frm.doc.status === "Draft" && !frm.is_new()) {
            frm.add_custom_button(__('✏️ Beschreibungen prüfen'), function() {
                frappe.call({
                    method: 'fieldservice.fieldservice.doctype.service_report.service_report.run_review',
                    args: { service_report: frm.doc.name },
                    callback: function(r) {
                        if (!r.message || r.message.length === 0) return;
                        show_review_dialog(frm, JSON.stringify(r.message));
                    }
                });
            }, __("Aktionen"));

            frm.add_custom_button(__('🤖 KI-Check'), function() {
                show_ai_loading();
                frappe.call({
                    method: 'fieldservice.fieldservice.doctype.service_report.service_report.run_llm_review',
                    args: { service_report: frm.doc.name },
                    callback: function(r) {
                        hide_ai_loading();
                        if (!r.message || r.message.length === 0) return;
                        show_review_dialog(frm, JSON.stringify(r.message));
                    },
                    error: function() {
                        hide_ai_loading();
                        // frappe.throw already shows the error dialog server-side,
                        // so we only need to remove the loading overlay here
                    }
                });
            }, __("Aktionen"));
        }

        // AI Review Log button (System Manager only)
        if (frappe.user_roles.includes('System Manager')) {
            frm.add_custom_button(__('📊 KI-Review Protokoll'), function() {
                show_ai_review_log(frm);
            }, __("Aktionen"));
        }

        // Fix Frappe grid column width bug (known issue: col-sm gets wrong values after reload)
        document.querySelectorAll('.form-column').forEach(el => {
            let match = el.className.match(/col-sm-(\d+)/);
            if (match) {
                let val = parseInt(match[1]);
                if (val > 12 || val < 4) {
                    el.classList.remove('col-sm-' + val);
                    el.classList.add('col-sm-12');
                }
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
		erpnext.utils.get_party_details(frm, null, null, function() {
			apply_preferred_customer_address(frm);
		});
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
		render_address_card(frm);
	},
	contact_person: function(frm) {
		erpnext.utils.get_contact_details(frm);
		render_contact_card(frm);
	},
});


// Render a styled address card into the read-only "address_card" HTML field.
function render_address_card(frm) {
	const fld = frm.fields_dict.address_card;
	if (!fld) return;
	const $w = fld.$wrapper;
	if (!frm.doc.customer_address) {
		$w.html(
			'<div class="sr-info-card" style="box-sizing:border-box;margin-bottom:16px;border:1px dashed var(--border-color);border-radius:8px;padding:12px 14px;'
			+ 'color:var(--text-muted);font-size:13px;">' + __('Keine Adresse ausgewählt') + '</div>'
		);
		equalize_info_cards(frm);
		return;
	}
	frappe.db.get_doc('Address', frm.doc.customer_address).then(a => {
		const esc = frappe.utils.escape_html;
		const rows = [];
		const title = frm.doc.customer_name || a.address_title || '';
		if (title) rows.push('<div style="font-weight:600;font-size:14px;">' + esc(title) + '</div>');
		if (a.address_line1) rows.push('<div>' + esc(a.address_line1) + '</div>');
		if (a.address_line2) rows.push('<div>' + esc(a.address_line2) + '</div>');
		const city = [a.pincode, a.city].filter(Boolean).map(esc).join(' ');
		if (city) rows.push('<div>' + city + '</div>');
		if (a.country) rows.push('<div>' + esc(a.country) + '</div>');
		const contacts = [];
		if (a.phone) contacts.push('☎ ' + esc(a.phone));
		if (a.email_id) contacts.push('✉ ' + esc(a.email_id));
		if (contacts.length) rows.push('<div style="margin-top:6px;color:var(--text-muted);font-size:12px;">' + contacts.join('&nbsp;&nbsp;') + '</div>');

		const maps = 'https://www.google.com/maps/search/?api=1&query='
			+ encodeURIComponent([a.address_line1, a.address_line2, a.pincode, a.city, a.country].filter(Boolean).join(', '));

		$w.html(
			'<div class="sr-info-card" style="box-sizing:border-box;margin-bottom:16px;border:1px solid var(--border-color);border-radius:8px;padding:12px 14px;'
			+ 'background:var(--card-bg, var(--fg-color));display:flex;gap:12px;align-items:flex-start;">'
			+ '<div style="font-size:22px;line-height:1;">📍</div>'
			+ '<div style="font-size:13px;line-height:1.55;flex:1;">' + rows.join('') + '</div>'
			+ '<a href="' + maps + '" target="_blank" title="' + __('In Google Maps öffnen') + '" '
			+ 'style="font-size:12px;white-space:nowrap;text-decoration:none;">🗺️ ' + __('Karte') + '</a>'
			+ '</div>'
		);
		equalize_info_cards(frm);
	});
}


// Render a styled contact card (all emails and phone numbers) into "contact_card".
function render_contact_card(frm) {
	const fld = frm.fields_dict.contact_card;
	if (!fld) return;
	const $w = fld.$wrapper;
	if (!frm.doc.contact_person) {
		$w.html(
			'<div class="sr-info-card" style="box-sizing:border-box;margin-bottom:16px;border:1px dashed var(--border-color);border-radius:8px;padding:12px 14px;'
			+ 'color:var(--text-muted);font-size:13px;">' + __('Kein Kontakt ausgewählt') + '</div>'
		);
		equalize_info_cards(frm);
		return;
	}
	frappe.db.get_doc('Contact', frm.doc.contact_person).then(c => {
		const esc = frappe.utils.escape_html;
		const rows = [];
		const name = [c.salutation, c.first_name, c.last_name].filter(Boolean).map(esc).join(' ') || esc(c.name);
		rows.push('<div style="font-weight:600;font-size:14px;">' + name + '</div>');
		const sub = [c.designation, c.company_name].filter(Boolean).map(esc).join(', ');
		if (sub) rows.push('<div style="color:var(--text-muted);font-size:12px;margin-bottom:4px;">' + esc(sub) + '</div>');

		(c.email_ids || []).forEach(e => {
			if (!e.email_id) return;
			const prim = e.is_primary ? ' <span style="color:var(--text-muted);">(' + __('primär') + ')</span>' : '';
			rows.push('<div>✉ <a href="mailto:' + encodeURIComponent(e.email_id) + '">' + esc(e.email_id) + '</a>' + prim + '</div>');
		});
		(c.phone_nos || []).forEach(p => {
			if (!p.phone) return;
			const icon = p.is_primary_mobile_no ? '📱' : '☎';
			rows.push('<div>' + icon + ' <a href="tel:' + encodeURIComponent(p.phone) + '">' + esc(p.phone) + '</a></div>');
		});
		if (rows.length === 1) rows.push('<div style="color:var(--text-muted);font-size:12px;">' + __('Keine Kontaktdaten hinterlegt') + '</div>');

		$w.html(
			'<div class="sr-info-card" style="box-sizing:border-box;margin-bottom:16px;border:1px solid var(--border-color);border-radius:8px;padding:12px 14px;'
			+ 'background:var(--card-bg, var(--fg-color));display:flex;gap:12px;align-items:flex-start;">'
			+ '<div style="font-size:22px;line-height:1;">👤</div>'
			+ '<div style="font-size:13px;line-height:1.55;flex:1;">' + rows.join('') + '</div>'
			+ '</div>'
		);
		equalize_info_cards(frm);
	});
}


// Make the address and contact cards the same height (align bottoms).
function equalize_info_cards(frm) {
	setTimeout(() => {
		const els = ['address_card', 'contact_card']
			.map(fn => frm.fields_dict[fn] && frm.fields_dict[fn].$wrapper.find('.sr-info-card')[0])
			.filter(Boolean);
		if (els.length < 2) return;
		els.forEach(el => { el.style.minHeight = ''; });
		const max = Math.max(...els.map(el => el.offsetHeight));
		els.forEach(el => { el.style.minHeight = max + 'px'; });
	}, 60);
}


// Quick-add buttons next to the hours sum: each adds a work position ending now
// and starting "minutes" ago, with a placeholder description to edit later.
const QUICK_ADD_DURATIONS = [
	{ label: '15', minutes: 15 },
	{ label: '30', minutes: 30 },
	{ label: '45', minutes: 45 },
	{ label: '1 Std.', minutes: 60 },
	{ label: '2 Std.', minutes: 120 },
];

function render_quick_add_buttons(frm) {
	const fld = frm.fields_dict.quick_add_buttons;
	if (!fld) return;
	const $w = fld.$wrapper.empty();
	if (frm.doc.docstatus !== 0) return; // only while editable
	const $row = $('<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;justify-content:flex-end;margin-top:23px;"></div>');
	$row.append('<span style="font-size:12px;color:var(--text-muted);margin-right:2px;">' + __('Schnell erfassen') + ':</span>');
	QUICK_ADD_DURATIONS.forEach(d => {
		const $b = $('<button type="button" class="btn btn-xs btn-default">' + frappe.utils.escape_html(d.label) + '</button>');
		$b.on('click', () => add_quick_work_position(frm, d.minutes));
		$row.append($b);
	});
	$w.append($row);
}

function add_quick_work_position(frm, minutes) {
	const end = frappe.datetime.now_datetime();
	const begin = moment(end, 'YYYY-MM-DD HH:mm:ss').subtract(minutes, 'minutes').format('YYYY-MM-DD HH:mm:ss');
	const row = frm.fields_dict.work.grid.add_new_row(); // fires work_add (service_type/employee/address defaults)
	frappe.model.set_value(row.doctype, row.name, 'begin', begin);
	frappe.model.set_value(row.doctype, row.name, 'end', end);
	frappe.model.set_value(row.doctype, row.name, 'description', __('Tätigkeit hier beschreiben …'));
	frm.refresh_field('work');
	frappe.show_alert({ message: __('Arbeitsposition ({0} Min.) hinzugefügt', [minutes]), indicator: 'green' });
}


// Prefill customer_address per Fieldservice Settings (billing vs shipping + fallback),
// overriding the billing-address default set by erpnext.utils.get_party_details.
function apply_preferred_customer_address(frm) {
	if (!frm.doc.customer) return;
	frappe.call({
		method: "fieldservice.api.get_preferred_customer_address",
		args: { customer: frm.doc.customer },
		callback: function(r) {
			frm.set_value("customer_address", r.message || null);
		}
	});
}


// item_name is populated via fetch_from "item_code.item_name" on the
// Service Report Item doctype; no client-side fetch needed (the old handler
// called frappe.client.get with an empty item_code -> "Item None not found").

frappe.ui.form.on('Service Report Work',{
    work_add(frm, cdt, cdn) {
        let address = frm.doc.customer_address,
            service_type = frm.doc.report_type,
            index = frappe.model.get_value(cdt,cdn,"idx");

        frappe.model.set_value(cdt,cdn,"service_type",service_type);
        frappe.model.set_value(cdt,cdn,"employee",frm.doc.employee);
        frappe.model.set_value (cdt,cdn,"address" , address);
        if (service_type === "On-Site Service" && index ===1){
            frappe.model.set_value(cdt,cdn,"travel_charges",1);
		

        }

        cur_frm.refresh_field("work");
    }
});


// ---------------------------------------------------------------------------
// AI Loading Overlay
// ---------------------------------------------------------------------------

function show_ai_loading() {
    if (document.getElementById('ai-loading-overlay')) return;
    let overlay = document.createElement('div');
    overlay.id = 'ai-loading-overlay';
    overlay.innerHTML = `
        <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:10000;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px);">
            <div style="background:#fff;border-radius:16px;padding:40px 50px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.3);max-width:400px;">
                <div style="width:60px;height:60px;margin:0 auto 20px;position:relative;">
                    <div style="position:absolute;width:60px;height:60px;border:3px solid #f0f0f0;border-top:3px solid #e73249;border-radius:50%;animation:ai-spin 1s linear infinite;"></div>
                    <div style="position:absolute;width:40px;height:40px;top:10px;left:10px;border:3px solid #f0f0f0;border-bottom:3px solid #1565c0;border-radius:50%;animation:ai-spin 0.7s linear infinite reverse;"></div>
                    <div style="position:absolute;width:20px;height:20px;top:20px;left:20px;border:3px solid #f0f0f0;border-top:3px solid #2e7d32;border-radius:50%;animation:ai-spin 0.5s linear infinite;"></div>
                </div>
                <div style="font-size:16px;font-weight:600;color:#333;margin-bottom:6px;">KI prüft Beschreibungen</div>
                <div style="font-size:13px;color:#888;" id="ai-loading-status">Texte werden analysiert...</div>
            </div>
        </div>
        <style>
            @keyframes ai-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
    `;
    document.body.appendChild(overlay);

    // Animate status text
    let messages = ['Texte werden analysiert...', 'Rechtschreibung wird geprüft...', 'Grammatik wird korrigiert...', 'Formulierungen werden verbessert...', 'Service-Typ wird bewertet...'];
    let idx = 0;
    overlay._interval = setInterval(() => {
        idx = (idx + 1) % messages.length;
        let el = document.getElementById('ai-loading-status');
        if (el) el.textContent = messages[idx];
    }, 2000);
}

function hide_ai_loading() {
    let overlay = document.getElementById('ai-loading-overlay');
    if (overlay) {
        clearInterval(overlay._interval);
        overlay.remove();
    }
}

// ---------------------------------------------------------------------------
// Change Service Type: Bulk Dialog
// ---------------------------------------------------------------------------

function show_change_service_type_dialog(frm, selected_rows) {
    // Read service_type options dynamically from doctype meta (single source of truth)
    let st_field = frappe.meta.get_docfield('Service Report Work', 'service_type');
    let options_str = (st_field && st_field.options)
        ? st_field.options
        : 'Remote Service\nOn-Site Service\nApplication Development';

    // Preselect if all selected rows share the same current service_type
    let unique_types = Array.from(new Set(selected_rows.map(r => r.service_type || '')));
    let default_type = (unique_types.length === 1 && unique_types[0]) ? unique_types[0] : '';

    let svc_colors = {
        'Remote Service':          {bg:'#e3f2fd', color:'#1565c0'},
        'On-Site Service':         {bg:'#fce4ec', color:'#c62828'},
        'Application Development': {bg:'#f3e5f5', color:'#6a1b9a'}
    };
    function badge(svc_type) {
        let c = svc_colors[svc_type] || {bg:'#f5f5f5', color:'#333'};
        let label = svc_type || '—';
        return '<span style="background:'+c.bg+';color:'+c.color+';padding:2px 8px;border-radius:10px;font-size:11px;white-space:nowrap;">'+label+'</span>';
    }

    function fmt_dt(dt) {
        if (!dt) return '';
        let d = new Date(dt);
        return d.toLocaleDateString('de-DE', {day:'2-digit', month:'2-digit'})
            + ' ' + d.toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
    }

    // Sort rows by idx for predictable display
    let rows = selected_rows.slice().sort((a, b) => (a.idx || 0) - (b.idx || 0));

    let total_hours = 0;
    let pos_1_row = null;
    let rows_html = rows.map(function(r) {
        total_hours += (r.hours || 0);
        if (r.idx === 1) pos_1_row = r;
        return '<tr style="border-top:1px solid #eee;">'
            + '<td style="padding:6px 8px;font-weight:600;white-space:nowrap;">Pos '+r.idx+'</td>'
            + '<td style="padding:6px 8px;">'+badge(r.service_type)+'</td>'
            + '<td style="padding:6px 8px;color:#666;font-size:12px;white-space:nowrap;">'+fmt_dt(r.begin)+' – '+fmt_dt(r.end)+'</td>'
            + '<td style="padding:6px 8px;text-align:right;font-weight:600;white-space:nowrap;">'+(r.hours || 0).toFixed(2)+' h</td>'
            + '<td style="padding:6px 8px;text-align:center;font-size:11px;color:#666;">'+(r.travel_charges ? '✈ Anfahrt' : '')+'</td>'
            + '</tr>';
    }).join('');

    let summary_html =
        '<div style="margin-bottom:8px;font-weight:600;">'+rows.length+' Position(en) ausgewählt</div>'
        + '<div style="border:1px solid var(--border-color);border-radius:6px;overflow:hidden;margin-bottom:6px;">'
        + '<table style="width:100%;font-size:13px;border-collapse:collapse;"><tbody>'+rows_html+'</tbody></table>'
        + '</div>'
        + '<div style="text-align:right;font-size:12px;color:#666;">Gesamt: <strong>'+total_hours.toFixed(2)+' h</strong></div>';

    let d = new frappe.ui.Dialog({
        title: __('Servicetyp ändern'),
        fields: [
            { fieldtype: 'HTML', fieldname: 'summary', options: summary_html },
            {
                fieldtype: 'Select',
                fieldname: 'new_service_type',
                label: __('Neuer Service-Typ'),
                options: options_str,
                default: default_type,
                reqd: 1
            },
            { fieldtype: 'HTML', fieldname: 'hint' }
        ],
        primary_action_label: __('Übernehmen'),
        primary_action(values) {
            let new_type = values.new_service_type;
            if (!new_type) {
                frappe.msgprint(__('Bitte einen Service-Typ wählen.'));
                return;
            }

            let travel_set_for_pos_1 = false;

            rows.forEach(function(row) {
                frappe.model.set_value(row.doctype, row.name, 'service_type', new_type);
                // Travel charges: set on Pos 1 when changing to On-Site (only if not already set)
                if (new_type === 'On-Site Service' && row.idx === 1 && !row.travel_charges) {
                    frappe.model.set_value(row.doctype, row.name, 'travel_charges', 1);
                    travel_set_for_pos_1 = true;
                }
            });

            frm.refresh_field('work');
            d.hide();

            let msg = __('Service-Typ für {0} Zeile(n) auf "{1}" geändert', [rows.length, new_type]);
            if (travel_set_for_pos_1) {
                msg += ' — ' + __('Anfahrt für Position 1 aktiviert');
            }
            frappe.show_alert({ message: msg, indicator: 'green' });
        }
    });

    // Reactive hint: travel_charges implications for Pos 1
    function update_hint() {
        let val = d.get_value('new_service_type');
        let html = '';

        if (pos_1_row && val) {
            let current = pos_1_row.service_type;
            let has_travel = !!pos_1_row.travel_charges;

            if (val === 'On-Site Service' && current !== 'On-Site Service' && !has_travel) {
                // Pos 1 wechselt auf On-Site → Anfahrt wird automatisch gesetzt
                html =
                    '<div style="margin-top:8px;padding:10px 14px;border:1px solid #ffcc80;border-left:4px solid #fb8c00;border-radius:4px;background:#fff3e0;font-size:13px;color:#bf360c;">'
                    + '✈ <strong>Position 1</strong> wechselt auf <em>On-Site Service</em> — die <strong>Anfahrt</strong> wird automatisch aktiviert.'
                    + '</div>';
            } else if (val === 'On-Site Service' && current !== 'On-Site Service' && has_travel) {
                // Pos 1 wechselt auf On-Site, Anfahrt schon gesetzt
                html =
                    '<div style="margin-top:8px;padding:10px 14px;border:1px solid #c8e6c9;border-left:4px solid #2e7d32;border-radius:4px;background:#e8f5e9;font-size:13px;color:#1b5e20;">'
                    + '✓ <strong>Position 1</strong> wechselt auf <em>On-Site Service</em>. Anfahrt ist bereits gesetzt.'
                    + '</div>';
            } else if (val !== 'On-Site Service' && current === 'On-Site Service' && has_travel) {
                // Pos 1 wechselt weg von On-Site, Anfahrt bleibt gesetzt → Hinweis
                html =
                    '<div style="margin-top:8px;padding:10px 14px;border:1px solid #bbdefb;border-left:4px solid #1976d2;border-radius:4px;background:#e3f2fd;font-size:13px;color:#0d47a1;">'
                    + 'ℹ <strong>Position 1</strong> wechselt von <em>On-Site</em> auf <em>'+val+'</em>. Die zuvor gesetzte <strong>Anfahrt</strong> bleibt unverändert und sollte ggf. manuell entfernt werden.'
                    + '</div>';
            }
        }

        d.fields_dict.hint.$wrapper.html(html);
    }

    d.show();
    d.fields_dict.new_service_type.$input.on('change', update_hint);
    update_hint();  // initial render based on default_type
}

// ---------------------------------------------------------------------------
// Review Pipeline: Confirm Dialog
// ---------------------------------------------------------------------------

function show_review_dialog(frm, fixes_data, from_submit) {
    let fixes;
    try {
        fixes = typeof fixes_data === 'string' ? JSON.parse(fixes_data) : fixes_data;
    } catch(e) {
        frappe.msgprint(__('Error parsing review data'));
        return;
    }

    // --- Helpers ---
    function strip_html(html) {
        return (html || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\s+/g, ' ').trim();
    }

    // Word-level diff for a single line
    function diff_words(orig_words, sugg_words) {
        let m = orig_words.length, n = sugg_words.length;
        let dp = Array.from({length: m+1}, () => Array(n+1).fill(0));
        for (let i=1; i<=m; i++) for (let j=1; j<=n; j++)
            dp[i][j] = orig_words[i-1]===sugg_words[j-1] ? dp[i-1][j-1]+1 : Math.max(dp[i-1][j], dp[i][j-1]);
        let result = [], i=m, j=n;
        while (i>0||j>0) {
            if (i>0&&j>0&&orig_words[i-1]===sugg_words[j-1]) { result.unshift({t:'eq',w:orig_words[i-1]}); i--;j--; }
            else if (j>0&&(i===0||dp[i][j-1]>=dp[i-1][j])) { result.unshift({t:'add',w:sugg_words[j-1]}); j--; }
            else { result.unshift({t:'del',w:orig_words[i-1]}); i--; }
        }
        return result.map(r =>
            r.t==='del' ? '<span style="background:#ffcdd2;text-decoration:line-through;padding:1px 2px;border-radius:2px;">'+r.w+'</span>' :
            r.t==='add' ? '<span style="background:#c8e6c9;padding:1px 2px;border-radius:2px;font-weight:500;">'+r.w+'</span>' : r.w
        ).join(' ');
    }

    // Extract bullet lines from HTML (<p>• text</p> or <li> or plain text)
    function extract_lines(html) {
        if (!html) return [];
        // Split on <p> tags
        let parts = html.split(/<\/?p>/).map(s => s.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').trim()).filter(s => s);
        if (parts.length > 1) return parts;
        // Split on <li> tags
        parts = html.split(/<\/?li[^>]*>/).map(s => s.replace(/<[^>]+>/g, '').trim()).filter(s => s);
        if (parts.length > 1) return parts;
        // Single line
        return [strip_html(html)];
    }

    // Line-by-line diff with word-level highlighting
    function diff_html(original_html, suggested_html) {
        let orig_lines = extract_lines(original_html);
        let sugg_lines = extract_lines(suggested_html);

        // Match lines by index (bullet lists have same structure)
        let max_len = Math.max(orig_lines.length, sugg_lines.length);
        let output = [];
        for (let i = 0; i < max_len; i++) {
            let ol = (i < orig_lines.length) ? orig_lines[i] : '';
            let sl = (i < sugg_lines.length) ? sugg_lines[i] : '';
            if (ol === sl) {
                output.push('<div style="margin-bottom:3px;">' + sl + '</div>');
            } else if (!ol) {
                output.push('<div style="margin-bottom:3px;"><span style="background:#c8e6c9;padding:1px 2px;border-radius:2px;font-weight:500;">' + sl + '</span></div>');
            } else if (!sl) {
                output.push('<div style="margin-bottom:3px;"><span style="background:#ffcdd2;text-decoration:line-through;padding:1px 2px;border-radius:2px;">' + ol + '</span></div>');
            } else {
                output.push('<div style="margin-bottom:3px;">' + diff_words(ol.split(/\s+/), sl.split(/\s+/)) + '</div>');
            }
        }
        return output.join('');
    }

    function format_date(dt) {
        if (!dt) return '';
        let d = new Date(dt);
        return d.toLocaleDateString('de-DE', {day:'2-digit',month:'2-digit',year:'numeric'})
            + ' ' + d.toLocaleTimeString('de-DE', {hour:'2-digit',minute:'2-digit'});
    }

    function svc_type_badge(svc_type) {
        let colors = {
            'Remote Service': {bg:'#e3f2fd',color:'#1565c0'},
            'On-Site Service': {bg:'#fce4ec',color:'#c62828'},
            'Application Development': {bg:'#f3e5f5',color:'#6a1b9a'}
        };
        let c = colors[svc_type] || {bg:'#f5f5f5',color:'#333'};
        return '<span style="background:'+c.bg+';color:'+c.color+';padding:2px 8px;border-radius:10px;font-size:11px;white-space:nowrap;">'+svc_type+'</span>';
    }

    function get_work_meta(idx) {
        if (idx < 0 || idx >= frm.doc.work.length) return null;
        let w = frm.doc.work[idx];
        return { begin: w.begin, end: w.end, hours: w.hours, service_type: w.service_type };
    }

    // --- Group fixes by position ---
    let grouped = {};
    let standalone = [];
    let hints = [];

    fixes.forEach(function(fix, index) {
        fix._index = index;
        if (fix.change_type === 'hint') {
            hints.push(fix);
            return;
        }
        let m = fix.field.match(/^work\[(\d+)\]/);
        if (m) {
            let key = 'work[' + m[1] + ']';
            if (!grouped[key]) grouped[key] = {};
            if (fix.field.endsWith('.service_type')) grouped[key].svc = fix;
            else grouped[key].desc = fix;
        } else if (fix.field === 'report_type') {
            standalone.push(fix);
        } else {
            standalone.push(fix);
        }
    });

    // --- Build dialog body ---
    let body = '<div class="review-results" style="font-size:13px;">';

    // Standalone fixes (titel, global report_type)
    standalone.forEach(function(fix) {
        let label = fix.field === 'titel' ? 'Titel' : (fix.field === 'report_type' ? 'Service-Typ (gesamter Report)' : fix.field);
        let is_svc = fix.field === 'report_type';
        let badge_html = is_svc
            ? '<span style="background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:10px;font-size:11px;margin-left:8px;">Service-Typ</span>'
            : '<span style="background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:10px;font-size:11px;margin-left:8px;">Korrektur</span>';
        let border = is_svc ? '#ff9800' : 'var(--border-color)';

        body += '<div style="margin-bottom:12px;padding:12px;border:1px solid '+border+';border-radius:6px;background:#fff;">';

        if (is_svc) {
            // Service type card with better layout
            body += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">';
            body += '<input type="checkbox" checked data-fix-index="'+fix._index+'" style="width:18px;min-width:18px;height:18px;flex-shrink:0;cursor:pointer;accent-color:#ff9800;">';
            body += '<strong style="font-size:14px;">'+label+'</strong>';
            body += '</div>';
            // Begründung
            let reason = fix.message.replace(/^Service-Typ:\s*/, '');
            body += '<div style="font-size:12px;color:#555;margin-bottom:10px;line-height:1.4;">'+reason+'</div>';
            // Badges
            body += '<div style="padding:8px 12px;background:#fff3e0;border-radius:4px;">';
            body += svc_type_badge(fix.original_value) + ' <span style="margin:0 8px;font-size:16px;">\u2192</span> ' + svc_type_badge(fix.suggested_value);
            body += '</div>';
        } else {
            body += '<div style="display:flex;align-items:center;margin-bottom:8px;">';
            body += '<input type="checkbox" checked data-fix-index="'+fix._index+'" style="width:18px;min-width:18px;height:18px;flex-shrink:0;margin-right:10px;cursor:pointer;accent-color:#e73249;">';
            body += '<strong>'+label+'</strong>'+badge_html;
            body += '<span style="color:var(--text-muted);margin-left:auto;font-size:12px;">'+fix.message+'</span>';
            body += '</div>';
            body += '<div style="padding:10px 14px;background:#fafafa;border-radius:4px;line-height:1.6;">'+diff_html(fix.original_value, fix.suggested_value)+'</div>';
        }
        body += '</div>';
    });

    // Grouped position fixes
    Object.keys(grouped).sort().forEach(function(key) {
        let group = grouped[key];
        let m = key.match(/work\[(\d+)\]/);
        let pos_idx = parseInt(m[1]);
        let pos_num = pos_idx + 1;
        let meta = get_work_meta(pos_idx);
        let has_svc = !!group.svc;
        let has_desc = !!group.desc;
        let border = has_svc ? '#ff9800' : 'var(--border-color)';

        body += '<div style="margin-bottom:12px;padding:12px;border:1px solid '+border+';border-radius:6px;background:#fff;">';

        // Position header with metadata
        body += '<div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #eee;">';
        body += '<strong style="font-size:14px;">Position '+pos_num+'</strong>';
        if (meta) {
            body += svc_type_badge(meta.service_type);
            body += '<span style="color:var(--text-muted);font-size:12px;">'+format_date(meta.begin)+' \u2013 '+format_date(meta.end)+'</span>';
            body += '<span style="color:var(--text-muted);font-size:12px;font-weight:600;">'+meta.hours+' Std.</span>';
        }
        body += '</div>';

        // Description correction
        if (has_desc) {
            let fix = group.desc;
            body += '<div style="display:flex;align-items:center;margin-bottom:6px;">';
            body += '<input type="checkbox" checked data-fix-index="'+fix._index+'" style="width:18px;min-width:18px;height:18px;flex-shrink:0;margin-right:10px;cursor:pointer;accent-color:#e73249;">';
            body += '<span style="background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:10px;font-size:11px;">Textkorrektur</span>';
            body += '<span style="color:var(--text-muted);margin-left:auto;font-size:12px;">'+fix.message+'</span>';
            body += '</div>';
            body += '<div style="padding:10px 14px;background:#fafafa;border-radius:4px;line-height:1.6;margin-bottom:6px;">'+diff_html(fix.original_value, fix.suggested_value)+'</div>';
            // Editable text field for custom formulation
            body += '<details style="margin-top:4px;"><summary style="cursor:pointer;font-size:12px;color:var(--text-muted);">Eigene Formulierung eingeben</summary>';
            let prefill_lines = extract_lines(fix.suggested_value);
            let prefill = prefill_lines.join('\n');
            let line_count = Math.max(prefill_lines.length, 3);
            let ta_height = (line_count * 22) + 20;
            body += '<textarea data-custom-text-index="'+fix._index+'" data-original-prefill="'+encodeURIComponent(prefill)+'" style="width:100%;height:'+ta_height+'px;margin-top:6px;padding:8px;border:1px solid #ddd;border-radius:4px;font-size:13px;font-family:inherit;resize:vertical;line-height:20px;">'+prefill+'</textarea>';
            body += '</details>';
        }

        // Service type suggestion
        if (has_svc) {
            let fix = group.svc;
            body += '<div style="'+(has_desc?'margin-top:10px;padding-top:10px;border-top:1px dashed #ddd;':'')+'display:flex;align-items:center;margin-bottom:6px;">';
            body += '<input type="checkbox" checked data-fix-index="'+fix._index+'" style="width:18px;min-width:18px;height:18px;flex-shrink:0;margin-right:10px;cursor:pointer;accent-color:#ff9800;">';
            body += '<span style="background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:10px;font-size:11px;">Service-Typ</span>';
            body += '<span style="color:var(--text-muted);margin-left:auto;font-size:12px;">'+fix.message+'</span>';
            body += '</div>';
            body += '<div style="padding:8px 12px;background:#fff3e0;border-radius:4px;">';
            body += svc_type_badge(fix.original_value) + ' <span style="margin:0 6px;">\u2192</span> ' + svc_type_badge(fix.suggested_value);
            body += '</div>';
        }

        body += '</div>';
    });

    // Hints section (informational, no checkbox)
    if (hints.length > 0) {
        body += '<div style="margin-top:16px;padding-top:12px;border-top:2px solid #e0e0e0;">';
        body += '<div style="display:flex;align-items:center;margin-bottom:10px;"><strong style="font-size:14px;">💡 Hinweise</strong></div>';
        hints.forEach(function(hint) {
            let pos_match = hint.field.match(/work\[(\d+)\]/);
            let pos_label = pos_match ? 'Position ' + (parseInt(pos_match[1]) + 1) : '';
            let meta = pos_match ? get_work_meta(parseInt(pos_match[1])) : null;

            body += '<div style="margin-bottom:10px;padding:10px 14px;border:1px solid #bbdefb;border-left:4px solid #1976d2;border-radius:4px;background:#e3f2fd;">';
            body += '<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">';
            body += '<span style="background:#bbdefb;color:#0d47a1;padding:2px 8px;border-radius:10px;font-size:11px;">Hinweis</span>';
            if (pos_label) {
                body += '<strong>' + pos_label + '</strong>';
                if (meta) body += ' ' + svc_type_badge(meta.service_type);
            }
            body += '</div>';
            body += '<div style="font-size:13px;color:#1a237e;">' + hint.message + '</div>';
            if (hint.original_value && hint.original_value !== hint.message) {
                body += '<div style="font-size:12px;color:#555;margin-top:4px;">' + hint.original_value + '</div>';
            }
            body += '</div>';
        });
        body += '</div>';
    }

    body += '</div>';

    let primary_label = from_submit ? __('Ausgewählte übernehmen & buchen') : __('Ausgewählte übernehmen');
    let secondary_label = from_submit ? __('Ohne Korrektur buchen') : __('Abbrechen');

    let d = new frappe.ui.Dialog({
        title: __('Beschreibungen prüfen'),
        size: 'extra-large',
        fields: [{fieldtype:'HTML', fieldname:'review_content', options:body}],
        primary_action_label: primary_label,
        primary_action: function() {
            // Collect ALL decisions (accepted/rejected) for logging
            let selected_fixes = [];
            let all_decisions = [];

            fixes.forEach(function(fix, index) {
                let cb = d.$wrapper.find('input[data-fix-index="'+index+'"]');
                let accepted = cb.length ? cb.is(':checked') : null;  // null for hints

                // Check for custom text override
                let custom_text = null;
                let custom_ta = d.$wrapper.find('textarea[data-custom-text-index="'+index+'"]');
                let applied_fix = Object.assign({}, fix);

                if (custom_ta.length) {
                    let current_val = custom_ta.val().trim();
                    let original_prefill = decodeURIComponent(custom_ta.attr('data-original-prefill') || '');
                    if (current_val && current_val !== original_prefill.trim()) {
                        custom_text = current_val;
                        let lines = current_val.split('\n').filter(l => l.trim());
                        let html = lines.map(l => {
                            l = l.trim().replace(/^[\u2022\-]\s*/, '');
                            return '<p>\u2022 ' + l + '</p>';
                        }).join('');
                        applied_fix = Object.assign({}, fix, {suggested_value: html});
                    }
                }

                all_decisions.push({fix: fix, accepted: accepted, custom_text: custom_text});

                if (accepted) {
                    selected_fixes.push(applied_fix);
                }
            });

            if (selected_fixes.length === 0) {
                frappe.msgprint(__('Keine Korrekturen ausgewählt.'));
                return;
            }

            d.hide();
            if (from_submit) {
                selected_fixes.forEach(function(fix) {
                    if (fix.field === 'titel') {
                        frm.doc.titel = fix.suggested_value;
                    } else if (fix.field === 'report_type') {
                        frm.doc.report_type = fix.suggested_value;
                    } else {
                        let fm = fix.field.match(/work\[(\d+)\]\.(description|service_type)/);
                        if (fm) {
                            let idx = parseInt(fm[1]);
                            if (idx < frm.doc.work.length) frm.doc.work[idx][fm[2]] = fix.suggested_value;
                        }
                    }
                });
                frm.refresh_field('work');
                frm.save().then(() => {
                    frm.call('submit', {flags:{skip_review:true}}).then(() => frm.reload_doc());
                });
            } else {
                frappe.call({
                    method: 'fieldservice.fieldservice.doctype.service_report.service_report.apply_review',
                    args: {
                        service_report: frm.doc.name,
                        fixes: JSON.stringify(selected_fixes),
                        all_decisions: JSON.stringify(all_decisions)
                    },
                    callback: function() { frm.reload_doc(); }
                });
            }
        },
        secondary_action_label: secondary_label,
        secondary_action: function() {
            d.hide();
            // pending_user_decision status in the log already documents the dismissal
            if (from_submit) {
                frm.call('submit', {flags:{skip_review:true}}).then(() => frm.reload_doc());
            }
        }
    });

    // No server calls on dismiss/close — the pending_user_decision
    // status logged by run_llm_review already documents the interaction

    d.$wrapper.find('.modal-dialog').css('max-width', '960px');
    d.show();

    // Auto-resize textareas when details is toggled open
    function autosize(ta) {
        ta.style.height = 'auto';
        ta.style.height = ta.scrollHeight + 'px';
    }
    d.$wrapper.find('details').on('toggle', function() {
        if (this.open) {
            let ta = this.querySelector('textarea');
            if (ta) setTimeout(() => autosize(ta), 10);
        }
    });
    // Also auto-resize on input
    d.$wrapper.find('textarea[data-custom-text-index]').on('input', function() {
        autosize(this);
    });
}

// ---------------------------------------------------------------------------
// AI Review Log Dialog (System Manager only)
// ---------------------------------------------------------------------------

function show_ai_review_log(frm) {
    let reviews = frm.doc.ai_reviews || [];

    let body = '<div style="font-size:13px;">';

    if (!reviews.length) {
        body += '<div style="text-align:center;padding:30px 20px;color:var(--text-muted);">';
        body += '<div style="font-size:32px;margin-bottom:10px;">📋</div>';
        body += '<div style="font-size:14px;">Noch keine KI-Reviews durchgeführt.</div>';
        body += '<div style="font-size:12px;margin-top:6px;">Verwende den Button <strong>🤖 KI-Check</strong> um eine Prüfung zu starten.</div>';
        body += '</div>';
    }

    reviews.slice().reverse().forEach(function(review, i) {
        let ts = frappe.datetime.str_to_user(review.timestamp);
        let total = (review.applied_count || 0) + (review.rejected_count || 0);

        body += '<div style="margin-bottom:16px;padding:14px;border:1px solid var(--border-color);border-radius:6px;background:#fff;">';

        // Header
        body += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #eee;">';
        body += '<strong style="font-size:14px;">Review #' + (reviews.length - i) + '</strong>';
        body += '<span style="color:var(--text-muted);font-size:12px;">' + ts + '</span>';
        body += '<span style="background:#f5f5f5;padding:2px 8px;border-radius:10px;font-size:11px;">' + (review.ai_model || '?') + '</span>';
        body += '<span style="margin-left:auto;">';
        if (review.applied_count) body += '<span style="background:#c8e6c9;color:#2e7d32;padding:2px 8px;border-radius:10px;font-size:11px;margin-right:4px;">✓ ' + review.applied_count + ' übernommen</span>';
        if (review.rejected_count) body += '<span style="background:#ffcdd2;color:#c62828;padding:2px 8px;border-radius:10px;font-size:11px;margin-right:4px;">✗ ' + review.rejected_count + ' abgelehnt</span>';
        if (review.hint_count) body += '<span style="background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:10px;font-size:11px;">💡 ' + review.hint_count + ' Hinweise</span>';
        body += '</span></div>';

        // Decisions detail
        try {
            let decisions = JSON.parse(review.user_decisions || '{}');
            let review_data = JSON.parse(review.review_data || '{}');
            let fixes = review_data.fixes || [];
            let decs = decisions.decisions || [];

            fixes.forEach(function(fix, j) {
                let dec = decs[j] || {};
                let accepted = dec.accepted;
                let icon, bg;
                if (accepted === true) { icon = '✓'; bg = '#e8f5e9'; }
                else if (accepted === false) { icon = '✗'; bg = '#fce4ec'; }
                else { icon = '💡'; bg = '#e3f2fd'; }

                let field_label = fix.field || '';
                let fm = field_label.match(/work\[(\d+)\]/);
                if (fm) field_label = 'Position ' + (parseInt(fm[1]) + 1);
                if (field_label === 'titel') field_label = 'Titel';
                if (field_label === 'report_type') field_label = 'Service-Typ';

                body += '<div style="display:flex;align-items:flex-start;gap:8px;padding:6px 8px;margin-bottom:4px;background:' + bg + ';border-radius:4px;font-size:12px;">';
                body += '<span style="font-size:14px;flex-shrink:0;">' + icon + '</span>';
                body += '<div style="flex:1;">';
                body += '<strong>' + field_label + '</strong>';
                if (fix.message) body += ' — <span style="color:#666;">' + fix.message + '</span>';
                if (dec.custom_text) body += '<div style="margin-top:4px;color:#555;font-style:italic;">Eigener Text: ' + dec.custom_text.substring(0, 100) + (dec.custom_text.length > 100 ? '...' : '') + '</div>';
                body += '</div></div>';
            });
        } catch(e) {
            body += '<div style="color:#999;font-size:12px;">Daten nicht lesbar</div>';
        }

        body += '</div>';
    });

    body += '</div>';

    let d = new frappe.ui.Dialog({
        title: __('KI-Review Protokoll'),
        size: 'extra-large',
        fields: [{fieldtype: 'HTML', fieldname: 'log_content', options: body}],
        primary_action_label: __('Schließen'),
        primary_action: function() { d.hide(); }
    });
    d.$wrapper.find('.modal-dialog').css('max-width', '900px');
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
