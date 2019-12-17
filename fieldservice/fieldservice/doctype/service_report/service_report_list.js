frappe.listview_settings['Service Report'] = {
	hide_name_column: true,

	onload: function(me) {
		if (!frappe.route_options) {
			frappe.route_options = {
				"owner": frappe.session.user,
				"status": "Open"
			};
		}
		me.page.set_title(__("Service Report"));
    }
}