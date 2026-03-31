// Copyright (c) 2022, itsdve GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fieldservice Settings', {
    refresh: function(frm) {
        if (frm.doc.enable_ai_review) {
            // Add "Modelle abrufen" button after ai_model field
            setTimeout(() => {
                let $model_field = frm.fields_dict.ai_model && frm.fields_dict.ai_model.$wrapper;
                if ($model_field && !$model_field.find('.fetch-models-btn').length) {
                    let $btn = $('<button class="btn btn-xs btn-default fetch-models-btn" style="margin-top:5px;">🔄 Modelle abrufen</button>');
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
                                let current = frm.doc.ai_model;
                                let options = r.message.map(m => m.id);
                                frm.set_df_property('ai_model', 'options', options.join('\n'));
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
                    $model_field.append($btn);
                }
            }, 500);
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
