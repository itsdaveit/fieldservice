frappe.provide('frappe.ui.form');

frappe.ui.form.ServiceReportQuickEntryForm = class ServiceReportQuickEntryForm extends frappe.ui.form.QuickEntryForm {
    constructor(doctype, after_insert, init_callback, doc, force) {
        super(doctype, after_insert, init_callback, doc, force);
        this.skip_redirect_on_error = true;
    }

    render_dialog() {
        super.render_dialog();

        let me = this;
        console.log("Dialog fields_dict:", me.dialog.fields_dict);

        // Ensure customer field is handled properly
        if (me.dialog.fields_dict && me.dialog.fields_dict.customer) {
            me.dialog.fields_dict.customer.get_query = function() {
                return {
                    filters: {
                        disabled: 0
                    }
                };
            };
        } else {
            console.error("Customer field not found or undefined in fields_dict.");
        }
    }
};


