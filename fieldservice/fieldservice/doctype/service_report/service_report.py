# -*- coding: utf-8 -*-
# Copyright (c) 2019, itsdve GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import datetime
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.contacts.doctype.address.address import get_address_display
from fieldservice.api import get_amount_of_hours
from fieldservice.validation import validate_service_report
from fieldservice.review_pipeline import build_default_pipeline

class ServiceReport(Document):
	def on_submit(self):
		self.status = "Submitted"
		self.save()
	
	def before_submit(self):
		# Skip review if flag is set (user chose to skip in confirm dialog)
		if not self.flags.get("skip_review"):
			self._run_review_pipeline()

		# Use the new validation function with throw_errors=True
		validate_service_report(self, throw_errors=True)

	def _run_review_pipeline(self):
		"""Run the review pipeline and apply or present corrections."""
		import json

		settings = frappe.get_single("Fieldservice Settings")
		review_mode = getattr(settings, "review_mode", "Off")
		if review_mode == "Off":
			return

		pipeline = build_default_pipeline(self)
		results = pipeline.run()
		fixes = pipeline.get_fixes()

		if not fixes:
			return

		if review_mode == "Auto-Apply":
			applied = pipeline.apply_auto_fixes()
			if applied:
				messages = [r.message for r in applied]
				frappe.msgprint(
					_("Beschreibungen automatisch korrigiert:") + "<br>" + "<br>".join(messages),
					indicator="green",
					alert=True
				)

		elif review_mode == "Confirm":
			frappe.throw(
				msg=json.dumps([r.to_dict() for r in fixes], ensure_ascii=False),
				title="review_required",
				exc=frappe.ValidationError
			)
	
	def before_save(self):
		# Skip validation warnings during timer start/stop
		if not self.flags.get("skip_validation"):
			# Use the new validation function with throw_errors=False
			errors = validate_service_report(self, throw_errors=False)

			# Display warnings if any
			if errors:
				warning_message = _("Warning: The following issues were found:") + "<br>"
				warning_message += "<br>".join(errors)
				warning_message += "<br><br>" + _("You can save the document, but these issues must be fixed before submission.")
				frappe.msgprint(warning_message, indicator="orange", alert=True)
		
		# Populate address display if address is set
		if self.customer_address:
			self.address_display = get_address_display(self.customer_address)
		elif not self.customer_address:
			self.address_display = ""

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
		report_doc.flags.skip_validation = True
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
		report_doc.flags.skip_validation = True
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
@frappe.whitelist()
def run_review(service_report):
	"""Run review pipeline and return fixes as JSON. Called from button."""
	import json
	from fieldservice.review_pipeline import build_default_pipeline

	doc = frappe.get_doc('Service Report', service_report)
	pipeline = build_default_pipeline(doc)
	results = pipeline.run()
	fixes = pipeline.get_fixes()

	if not fixes:
		frappe.msgprint(_('Keine Korrekturen nötig.'), indicator='green')
		return []

	return [r.to_dict() for r in fixes]

@frappe.whitelist()
def apply_review(service_report, fixes):
	"""Apply review fixes to work descriptions and save."""
	import json

	doc = frappe.get_doc('Service Report', service_report)
	if isinstance(fixes, str):
		fixes = json.loads(fixes)

	import re
	applied = 0
	for fix in fixes:
		m = re.match(r'work\[(\d+)\]\.description', fix.get('field', ''))
		if m and fix.get('suggested_value'):
			idx = int(m.group(1))
			if idx < len(doc.work):
				doc.work[idx].description = fix['suggested_value']
				applied += 1

	if applied:
		doc.flags.skip_validation = True
		doc.save()
		frappe.msgprint(
			_('{0} Beschreibung(en) korrigiert.').format(applied),
			indicator='green'
		)

	return applied
