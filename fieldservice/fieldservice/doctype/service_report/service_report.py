# -*- coding: utf-8 -*-
# Copyright (c) 2019, itsdve GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import datetime
import frappe
from frappe.model.document import Document



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
def stop_timer(service_report):
	report_doc = frappe.get_doc("Service Report", service_report)
	if report_doc.status == "Started":
		report_doc.timer_start = ""
		report_doc.status = "Draft"
		report_doc.save()
	else:
		frappe.throw("Timer is not started. Can`t stop the timmer.")
	


