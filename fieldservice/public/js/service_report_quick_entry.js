// frappe.provide('frappe.ui.form');

// frappe.ui.form.ServiceReportQuickEntryForm = class ServiceReportQuickEntryForm extends frappe.ui.form.QuickEntryForm {
//     constructor(doctype, after_insert, init_callback, doc, force) {
//         super(doctype, after_insert, init_callback, doc, force);
//         this.skip_redirect_on_error = true;
//     }


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

        // Customize fields here as needed
        if (me.dialog.fields_dict && me.dialog.fields_dict.project) {
            // Define onchange event for 'project' field
            me.dialog.fields_dict.project.df.onchange = function() {
                let selected_project = me.dialog.fields_dict.project.get_value();

                if (selected_project) {
                    // Fetch the standard_project from Fieldservice Settings
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

                                // Compare selected project with standard_project
                                if (selected_project !== standard_project) {
                                    // Fetch and set customer value if projects are different
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
                                                me.dialog.trigger('customer'); // Trigger the customer function after setting the customer field
                                            }
                                        }
                                    });
                                } else {
                                    // Clear customer field if project is equal to standard_project
                                    me.dialog.set_value('customer', '');
                                }
                            }
                        }
                    });
                } else {
                    // Clear customer field if no project is selected
                    me.dialog.set_value('customer', '');
                }
            };
        } else {
            console.error("Project field not found or undefined in fields_dict.");
        }

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




