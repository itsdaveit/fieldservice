frappe.provide('frappe.ui.form');

frappe.ui.form.ServiceReportQuickEntryForm = frappe.ui.form.QuickEntryForm.extend({
    init: function(doctype, after_insert, init_callback, doc, force) {
        this._super(doctype, after_insert, init_callback, doc, force);
        this.skip_redirect_on_error = true;
    },

    render_dialog: function() {
		//this.mandatory = this.mandatory.concat(this.get_variant_fields());
		this._super();
		console.log("hi")
		let me = this
		console.log(me)
        console.log(me.dialog.fields_dict)
        // Überprüfen, ob das customer-Feld in fields_dict vorhanden und definiert ist
        if (me.dialog.fields_dict && me.dialog.fields_dict.customer) {
            me.dialog.fields_dict.customer.get_query = function() {
                return {
                    filters: {
                        'disabled': 0
                    }
                };
            };
        } else {
            console.error("Customer field not found or undefined in fields_dict.");


         }
    }
});



