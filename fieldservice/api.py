from __future__ import unicode_literals

import json
import frappe
import frappe.handler
import frappe.client

def get_work_units_for_position(work_position, report_type):
    #Logic for rounding and minimum Quantity: (TBD)
    if report_type == "Remote Service":
        return 1
    
    if report_type == "On-Site Service":
        return 1

    return False

def get_items_from_work_positions(work_positions):
    pass

@frappe.whitelist()
def create_delivery_note(service_report):
    report_doc = frappe.get_doc("Service Report", service_report)
    items = []
    print(report_doc["customer"])
    #if(len(report_doc.work) > 0):
    #    items.append(get_items_from_work_positions(work))
    #if(len(report_doc.items) > 0):
    #    items.append(get_items_from_sr_items(items))
    
    return report_doc