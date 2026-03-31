// Copyright (c) 2022, itsdve GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fieldservice Settings', {
    refresh: function(frm) {
        // Add "Modelle abrufen" button next to ai_model field
        if (frm.fields_dict.ai_model) {
            frm.fields_dict.ai_model.$wrapper.find('.fetch-models-btn').remove();
            let $btn = $('<button class="btn btn-xs btn-default fetch-models-btn" style="margin-left:8px;margin-top:-2px;">🔄 Modelle abrufen</button>');
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
                        let options = r.message.map(m => m.id).join('\n');
                        // Update field options dynamically
                        frm.fields_dict.ai_model.df.fieldtype = 'Select';
                        frm.fields_dict.ai_model.df.options = options;
                        frm.fields_dict.ai_model.refresh();
                        frappe.show_alert({
                            message: r.message.length + ' Modelle geladen',
                            indicator: 'green'
                        });
                    }
                });
            });
            frm.fields_dict.ai_model.$wrapper.find('.control-label, .like-disabled-input, .control-value').first().after($btn);
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
