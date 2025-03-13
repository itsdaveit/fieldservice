# -*- coding: utf-8 -*-
# Copyright (c) 2019, itsdve GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import datetime
import frappe
from frappe.model.document import Document
from frappe import _
from fieldservice.api import get_amount_of_hours
from fieldservice.validation import validate_service_report

class ServiceReport(Document):
	def on_submit(self):
		self.status = "Submitted"
		self.save()
	
	def before_submit(self):
		# Use the new validation function with throw_errors=True
		validate_service_report(self, throw_errors=True)
	
	def before_save(self):
		# Use the new validation function with throw_errors=False
		errors = validate_service_report(self, throw_errors=False)
		
		# Display warnings if any
		if errors:
			warning_message = _("Warning: The following issues were found:") + "<br>"
			warning_message += "<br>".join(errors)
			warning_message += "<br><br>" + _("You can save the document, but these issues must be fixed before submission.")
			frappe.msgprint(warning_message, indicator="orange", alert=True)
		
		# Calculate hours
		hours_list = []
		for workposition in self.work:
			if workposition.begin and workposition.end:
				hours = get_amount_of_hours(workposition.begin, workposition.end)
				workposition.hours = hours 
				hours_list.append(hours)
		hours_sum = sum(hours_list)
		self.hours_sum = hours_sum


@frappe.whitelist()
def start_timer(service_report):
	report_doc = frappe.get_doc("Service Report", service_report)
	if report_doc.status == "Draft":
		report_doc.timer_start = datetime.now()
		report_doc.status = "Started"
		report_doc.save()
	else:
		frappe.throw("Timer is not stopped. Can`t start the timmer.")


@frappe.whitelist()
def stop_timer(service_report, description):
	report_doc = frappe.get_doc("Service Report", service_report)
	if report_doc.status == "Started":
		duration = datetime.now() -  report_doc.timer_start
		work_doc = frappe.get_doc({
			"doctype": "Service Report Work",
			"begin": report_doc.timer_start,
			"end": datetime.now(),
			"description": description if description != """<div class="ql-editor read-mode"><p><br></p></div>""" else _("Entry created by timer. Replace with work description."),
			"service_type" : report_doc.report_type,
			"address": report_doc.customer_address
			})
		report_doc.append("work", work_doc)
		for work in report_doc.work:
			if work == work_doc:
				num_work = work.idx
				if num_work == 1 and work.service_type == "On-Site Service":
					work.travel_charges = 1
		report_doc.timer_start = ""
		report_doc.status = "Draft"
		report_doc.save()

	else:
		frappe.throw("Timer is not started. Can`t stop the timmer.")

@frappe.whitelist()
def toggle_timer(service_report):
	report_doc = frappe.get_doc("Service Report", service_report)
	if report_doc.status == "Started":
		description = _("Entry created by List View button. Replace with work description.")
		stop_timer(service_report, description)
		return "Timer stopped"
	if report_doc.status == "Draft":
		start_timer(service_report)
		return "Timer started" 