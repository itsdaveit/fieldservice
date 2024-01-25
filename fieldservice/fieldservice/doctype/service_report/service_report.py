# -*- coding: utf-8 -*-
# Copyright (c) 2019, itsdve GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import datetime
import frappe
from frappe.model.document import Document
from frappe import _
from fieldservice.api import get_amount_of_hours

class ServiceReport(Document):
	def on_submit(self):
		self.status = "Submitted"
		self.save()
	
	def before_submit(self):
		from fieldservice.api import validate_work_duration, validate_empty_work_description, validate_start_before_end, validate_work_items
		validate_work_duration(self)
		validate_empty_work_description(self)
		validate_start_before_end(self)
		validate_work_items(self)
	
	def before_save(self):
		from fieldservice.api import validate_work_duration, validate_empty_work_description, validate_start_before_end, validate_work_items, validate_empty_work_item_address
		if self.work:
			validate_work_duration(self)
			validate_empty_work_description(self)
			validate_start_before_end(self)
		#validate_work_items(self)
		#validate_empty_work_item_address(self)
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
		frappe.throw(_("Timer is not stopped. Can`t start the timmer."))


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


