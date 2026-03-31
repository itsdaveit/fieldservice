// Copyright (c) 2022, itsdve GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fieldservice Settings', {
    refresh: function(frm) {
        // Add "Modelle abrufen" button next to ai_model field
        if (frm.fields_dict.ai_model && frm.doc.enable_ai_review) {
            frm.fields_dict.ai_model.$wrapper.find('.fetch-models-btn').remove();
            let $btn = $('<button class="btn btn-xs btn-default fetch-models-btn" style="margin-left:8px;">🔄 Modelle abrufen</button>');
            $btn.on('click', function() {
                frappe.call({
                    method: 'fieldservice.fieldservice.doctype.fieldservice_settings.fieldservice_settings.fetch_ai_models',
                    freeze: true,
                    freeze_message: 'Modelle werden abgerufen...',
                    callback: function(r) {
                        if (!r.message || r.message.length === 0) {
                            frappe.msgprint('Keine Modelle gefunden.');
                            return;
                        }
                        // Build options string and update the Select field
                        let current = frm.doc.ai_model;
                        let options = r.message.map(m => m.id);
                        frm.set_df_property('ai_model', 'options', options.join('\n'));
                        // Keep current selection if still valid
                        if (current && options.includes(current)) {
                            frm.set_value('ai_model', current);
                        }
                        frm.refresh_field('ai_model');
                        frappe.show_alert({
                            message: r.message.length + ' Modelle geladen',
                            indicator: 'green'
                        });
                    }
                });
            });
            frm.fields_dict.ai_model.$wrapper.find('.frappe-control').append($btn);
        }

        // Load default system prompt if empty
        if (frm.doc.enable_ai_review && !frm.doc.ai_system_prompt) {
            frappe.call({
                method: 'fieldservice.fieldservice.doctype.fieldservice_settings.fieldservice_settings.get_default_prompt',
                callback: function(r) {
                    if (r.message && !frm.doc.ai_system_prompt) {
                        frm.set_value('ai_system_prompt', r.message);
                    }
                }
            });
        }
    }
});
