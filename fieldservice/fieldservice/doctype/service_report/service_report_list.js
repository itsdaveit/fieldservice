frappe.listview_settings['Service Report'] = {
	hide_name_column: true,
    add_fields: ["status", "name"],

	onload: function(me) {
        frappe.call({
            method: "frappe.client.get_value",
            async:false,
            args:{
                doctype:'Employee',
                filters:{
                    user_id:frappe.user.name
                },
                fieldname:['name']
            },
            callback:function (r) {
                if(r.message != undefined){
                    frappe.route_options = {
                        "employee": r.message.name,
                        "docstatus": "Open"
                    };
                    console.log(r.message.name)
                };
                
            }
        });
		
		me.page.set_title(__("Service Report"));
    },

    has_indicator_for_draft: true,

	get_indicator: function (doc) {
        console.log("state")
        console.log(doc.status)
		if (doc.status == "Delivered") {
			return [__("Delivered"), "green", "status,=,Delivered"];
		} else if (doc.status == "Submitted") {
			return [__("Submitted"), "blue", "status,=,Submitted"];
        } else if (doc.status == "Draft") {
			return [__("Draft"), "red", "status,=,Draft"];
        } else if (doc.status == "Started") {
			return [__("Started"), "yellow", "status,=,Started"];
        }
    },
    button: {
        show(doc) {
            return doc.reference_name;
        },
        get_label() {
            return 'View';
        },
        get_description(doc) {
            return __('View {0}', [`${doc.reference_type} ${doc.reference_name}`])
        },
        action(doc) {
            frappe.set_route('Form', doc.reference_type, doc.reference_name);
        }
    },

}