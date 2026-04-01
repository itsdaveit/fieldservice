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
def apply_review(service_report, fixes, all_decisions=None):
	"""Apply review fixes and log AI review decisions."""
	import json

	doc = frappe.get_doc('Service Report', service_report)
	if isinstance(fixes, str):
		fixes = json.loads(fixes)

	import re
	applied = 0
	for fix in fixes:
		field = fix.get('field', '')
		suggested = fix.get('suggested_value')
		if not suggested:
			continue

		if field == 'titel':
			doc.titel = suggested
			applied += 1
		elif field == 'report_type':
			doc.report_type = suggested
			applied += 1
		else:
			m = re.match(r'work\[(\d+)\]\.(description|service_type)', field)
			if m:
				idx = int(m.group(1))
				attr = m.group(2)
				if idx < len(doc.work):
					setattr(doc.work[idx], attr, suggested)
					applied += 1

	# Update the most recent pending AI review entry with user decisions
	if all_decisions:
		decisions = json.loads(all_decisions) if isinstance(all_decisions, str) else all_decisions
		user_decisions = json.dumps({
			'decisions': [{
				'field': d.get('fix', {}).get('field', ''),
				'accepted': d.get('accepted'),
				'custom_text': d.get('custom_text')
			} for d in decisions]
		}, ensure_ascii=False)

		accepted_count = sum(1 for d in decisions if d.get('accepted') is True)
		rejected_count = sum(1 for d in decisions if d.get('accepted') is False)
		hint_count = sum(1 for d in decisions if d.get('accepted') is None)

		# Find the last pending review entry and update it
		last_review = None
		for review in reversed(doc.ai_reviews or []):
			if 'pending_user_decision' in (review.user_decisions or ''):
				last_review = review
				break

		if last_review:
			last_review.user_decisions = user_decisions
			last_review.applied_count = accepted_count
			last_review.rejected_count = rejected_count
			last_review.hint_count = hint_count
		else:
			# No pending entry found — create a new one
			settings = frappe.get_single('Fieldservice Settings')
			doc.append('ai_reviews', {
				'timestamp': frappe.utils.now(),
				'ai_model': getattr(settings, 'ai_model', '') or '',
				'review_data': json.dumps({'fixes': [d.get('fix', {}) for d in decisions]}, ensure_ascii=False),
				'user_decisions': user_decisions,
				'applied_count': accepted_count,
				'rejected_count': rejected_count,
				'hint_count': hint_count,
			})

	doc.flags.skip_validation = True
	doc.save()

	if applied:
		frappe.msgprint(
			_('{0} Beschreibung(en) korrigiert.').format(applied),
			indicator='green'
		)

	return applied

@frappe.whitelist()
def run_llm_review(service_report):
	"""Run LLM-based text correction on a Service Report."""
	from fieldservice.review_pipeline import build_default_pipeline, LLMTextCorrectionStep

	settings = frappe.get_single('Fieldservice Settings')
	if not getattr(settings, 'enable_ai_review', False):
		frappe.throw(_('KI-Review ist nicht aktiviert. Bitte in den Fieldservice Settings aktivieren.'))

	api_key = settings.get_password('ai_api_key')
	if not api_key:
		frappe.throw(_('Kein Anthropic API Key hinterlegt. Bitte in den Fieldservice Settings eintragen.'))

	doc = frappe.get_doc('Service Report', service_report)

	# Run deterministic steps first and apply them
	pipeline = build_default_pipeline(doc)
	pipeline.run()
	applied = pipeline.apply_auto_fixes()

	# Save if deterministic fixes were applied
	if applied:
		doc.flags.skip_validation = True
		doc.save()

	# Run LLM step
	model = getattr(settings, 'ai_model', None) or 'claude-sonnet-4-20250514'
	system_prompt = getattr(settings, 'ai_system_prompt', None) or ''

	step = LLMTextCorrectionStep(api_key, model, system_prompt)
	results = step.execute(doc, pipeline.results)

	# Log the query even if no corrections were suggested
	import json
	result_dicts = [r.to_dict() for r in results]
	review_data = json.dumps({'fixes': result_dicts}, ensure_ascii=False)

	# Count suggestions and hints
	suggestion_count = sum(1 for r in results if r.change_type in ('suggestion', 'auto_fix'))
	hint_count = sum(1 for r in results if r.change_type == 'hint')

	# Always log the AI query
	doc.append('ai_reviews', {
		'timestamp': frappe.utils.now(),
		'ai_model': model,
		'review_data': review_data,
		'user_decisions': json.dumps({
			'decisions': [],
			'note': 'no_corrections_needed' if not results else 'pending_user_decision'
		}, ensure_ascii=False),
		'applied_count': 0,
		'rejected_count': suggestion_count,  # default: all rejected until user decides
		'hint_count': hint_count,
	})
	doc.flags.skip_validation = True
	doc.save()

	if not results:
		frappe.msgprint(_('Keine KI-Korrekturen nötig.'), indicator='green')
		return []

	return result_dicts
