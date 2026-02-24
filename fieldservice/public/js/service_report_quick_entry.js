frappe.provide('frappe.ui.form');

frappe.ui.form.ServiceReportQuickEntryForm = class ServiceReportQuickEntryForm extends frappe.ui.form.QuickEntryForm {
    constructor(doctype, after_insert, init_callback, doc, force) {
        super(doctype, after_insert, init_callback, doc, force);
        this.skip_redirect_on_error = true;
    }

    render_dialog() {
        super.render_dialog();

        let me = this;

        // Customize project field — sync customer from project
        if (me.dialog.fields_dict && me.dialog.fields_dict.project) {
            me.dialog.fields_dict.project.df.onchange = function() {
                let selected_project = me.dialog.fields_dict.project.get_value();

                if (selected_project) {
                    frappe.call({
                        method: "frappe.client.get_value",
                        args: {
                            doctype: 'Fieldservice Settings',
                            filters: {},
                            fieldname: ['standard_project']
                        },
                        callback: function(r) {
                            if (r && r.message && r.message.standard_project) {
                                let standard_project = r.message.standard_project;

                                if (selected_project !== standard_project) {
                                    frappe.call({
                                        method: "frappe.client.get_value",
                                        args: {
                                            doctype: 'Project',
                                            filters: {
                                                name: selected_project
                                            },
                                            fieldname: ['customer']
                                        },
                                        callback: function(r) {
                                            if (r && r.message && r.message.customer) {
                                                me.dialog.set_value('customer', r.message.customer);
                                                me.dialog.trigger('customer');
                                            }
                                        }
                                    });
                                } else {
                                    me.dialog.set_value('customer', '');
                                }
                            }
                        }
                    });
                } else {
                    me.dialog.set_value('customer', '');
                }
            };
        }

        // Ensure customer field filters only active customers
        if (me.dialog.fields_dict && me.dialog.fields_dict.customer) {
            me.dialog.fields_dict.customer.get_query = function() {
                return {
                    filters: {
                        disabled: 0
                    }
                };
            };
        }
    }
};
