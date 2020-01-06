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

def get_amount_of_hours(begin, end, report_doc):
    timediff = end - begin
    print("beginn: " + str(begin) + " end: " + str(end))
    modulus = (timediff.seconds / 3600) % 1
    print("mod: " + str(modulus))
    print("timediff: " + str(timediff.seconds))
    full_hours = (timediff.seconds / 3600) - modulus
    print("full: " + str(full_hours))
    broken_hour = 0.0
    if modulus == 0.0:
        broken_hour = 0.0
    if modulus > 0.0 and modulus <= 0.25:
        broken_hour = 0.25
    if modulus > 0.25 and modulus <= 0.5:
        broken_hour = 0.5
    if modulus > 0.5 and modulus <= 0.75:
        broken_hour = 0.75
    if modulus > 0.75 and modulus <= 1:
        broken_hour = 1
    hours_rounded = 0
    hours_rounded = hours_rounded + (timediff.days * 24) 
    hours_rounded = hours_rounded + full_hours
    hours_rounded = hours_rounded + broken_hour
    return hours_rounded

def get_work_item_description(item_code, description, begin, end):
    work_item_doc = frappe.get_doc("Item", item_code)
    item_description = work_item_doc.description + "<br>" + begin.strftime("%d.%m.%Y %H:%M") + " - " + end.strftime("%d.%m.%Y %H:%M") + " Uhr"
    item_description = item_description + "<br>" + description
    
    return item_description


def get_items_from_sr_work(work_positions, report_doc):
    delivery_note_items = []
    employee_item = frappe.get_all('Employee Item Assignment', 
                                    filters={'employee': report_doc.employee,
                                            'service_type': report_doc.report_type},
                                    fields={'name', 'item'}
                                    )
    if len(employee_item) != 1:
        frappe.throw('Employee Item Assignment Mehrdeutig oder nicht gefunden.')
    
    
    item_code = employee_item[0].item
    print( "########### " + item_code)

    
    for work_position in work_positions:
        qty = get_amount_of_hours(work_position.begin, work_position.end, report_doc)
        delivery_note_item = frappe.get_doc({"doctype": "Delivery Note Item",
                                                "item_code": item_code,
                                                "description": work_position.description,
                                                "qty": qty
                                                })
        
        delivery_note_item.description = get_work_item_description(item_code, work_position.description, work_position.begin, work_position.end)
        print(delivery_note_item.name)
        delivery_note_items.append(delivery_note_item)
    return delivery_note_items
    

def get_items_from_sr_items(items):
    delivery_note_items = []
    for item in items:
        #print(item.name)
        #print(item.item)
        #print(item.amount)
        delivery_note_item = frappe.get_doc({"doctype": "Delivery Note Item",
                                                "item_code": item.item,
                                                "description": item.item_name,
                                                "qty": item.amount
                                                })
        delivery_note_items.append(delivery_note_item)
    return delivery_note_items

def create_delivery_note_items(items):
    pass

@frappe.whitelist()
def create_delivery_note(service_report):
    report_doc = frappe.get_doc("Service Report", service_report)
    items = []

    if(len(report_doc.work) > 0):
        items = items + get_items_from_sr_work(report_doc.work, report_doc)
    if(len(report_doc.items) > 0):
        items = items + get_items_from_sr_items(report_doc.items)


    if len(items) > 0:
        delivery_note_doc = frappe.get_doc({"doctype": "Delivery Note",
                                            "title": "Lieferschein zu " + report_doc.name,
                                            "customer": report_doc.customer,
                                            "status": "Draft",
                                            "company": frappe.get_doc("Global Defaults").default_company,
                                            "delivery_note_introduction_text": "Lieferschein zu Serviceprotokoll " + report_doc.name,
                                            })
        print(delivery_note_doc.customer)
        for item in items:
            delivery_note_doc.append("items", item)

        DN = frappe.get_doc("Delivery Note", delivery_note_doc.insert().name)
        frappe.msgprint("Lieferschein <a href=\"/desk#Form/Delivery%20Note/" + DN.name + "\">" + DN.name + "</a> erstellt.")
            
    else:
        frappe.throw('Keine abrechenbaren Positionen vorhanden.')

    
    
