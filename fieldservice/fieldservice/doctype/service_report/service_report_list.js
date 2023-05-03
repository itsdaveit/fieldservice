
frappe.listview_settings['Service Report'] = {
    

    button: {
        show: function(doc) {
            return true;
        },
        get_label: function() {
            return __('<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style="display: inline-block; vertical-align: text-bottom;"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm7-3.25v2.992l2.028.812a.75.75 0 0 1-.557 1.392l-2.5-1A.751.751 0 0 1 7 8.25v-3.5a.75.75 0 0 1 1.5 0Z"></path></svg>');
        },
        get_description: function(doc) {
            return __('Toggle Timer {0}', [doc.name])
        },
        action: function(doc) {
            //frappe.set_route("/app/print/Invoice/" + doc.name);
            frappe.call({
                "method": "fieldservice.fieldservice.doctype.service_report.service_report.toggle_timer",
                args: {
                    "service_report": doc.name,             
                },
                callback: (response) => {
                    msgprint(response.message);
                    frappe.ui.refresh('Service Report');
                } 
            })
              
        }
    },


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
                        "docstatus": "Open",
                        "status": "Draft"

                    };
                    console.log(r.message.name)
                };
                
            }
        });
		
		me.page.set_title(__("Service Report"));
    },

    has_indicator_for_draft: true,

	get_indicator: function (doc) {
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
   
}