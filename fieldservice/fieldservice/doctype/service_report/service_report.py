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

class ServiceReport(Document):

	def on_submit(self):
		self.status = "Submitted"
		self.save()

	def before_submit(self):
		# Use the new validation function with throw_errors=True
		validate_service_report(self, throw_errors=True)

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
def add_travel(docname, distance):
    doc = frappe.get_doc("Service Report", docname)

    # Aktualisiere die Distance, falls übergeben
    if distance is not None:
        doc.distance = int(distance)  # Stelle sicher, dass distance ein Integer ist

    # Überprüfen, ob distance > 0
    if doc.distance <= 0:
        frappe.throw(_("Bitte gefahrene Kilometer hinzufügen."))

    settings = frappe.get_single("Fieldservice Settings")
    travel_item = settings.travel_item
    travel_item_doc = frappe.get_doc("Item", travel_item)

    item_price_li = frappe.get_all(
        "Item Price",
        filters={"item_code": travel_item},
        fields="price_list_rate"
    )

    item_price = item_price_li[0].price_list_rate if item_price_li else 0

    # Prüfen, ob der Artikel bereits hinzugefügt wurde
    if any(item.item_code == travel_item for item in doc.items):
        frappe.throw(_("Anfahrt wurde bereits hinzugefügt."))

    if not travel_item:
        frappe.throw(_("Kein Anfahrt Artikel in den Einstellungen konfiguriert."))

    # Füge den Artikel in die Child-Tabelle hinzu
    doc.append("items", {
        "item_code": travel_item,
        "qty": doc.distance,
        "item_name": travel_item_doc.item_name,
        "rate": item_price
    })

    # Dokument speichern
    doc.save()


@frappe.whitelist()
def create_materialbedarf(service_report_name, customer):
    # Neues Dokument vom Doctype "Materialbedarf" erstellen
    materialbedarf_doc = frappe.get_doc({
        'doctype': 'Materialbedarf',
        'customer': customer,
        'service_report': service_report_name
    })

    # Dokument speichern
    materialbedarf_doc.insert()

    # Link zum neuen Dokument erstellen
    materialbedarf_link = frappe.utils.get_link_to_form("Materialbedarf", materialbedarf_doc.name)

    # Nachricht anzeigen
    msg_text = _("Materialbedarf {} wurde erstellt.").format(materialbedarf_link)
    frappe.msgprint(msg_text)
