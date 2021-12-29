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
    	
	get_indicator: function (doc) {
		if (doc.status === "Delivered") {
			return [__("Delivered"), "green", "status,=,Delivered"];
		} else if (doc.status === "Submitted") {
			return [__("Submitted"), "blue", "status,=,Submitted"];
        } else if (doc.status === "Draft") {
			return [__("Draft"), "orange", "status,=,Draft"];
        }
    }

}