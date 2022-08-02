from __future__ import unicode_literals

import json
from time import strftime, strptime
import frappe
import frappe.handler
import frappe.client
from datetime import datetime

def get_work_units_for_position(work_position, report_type):
    #Logic for rounding and minimum Quantity: (TBD)
    if report_type == "Remote Service":
        return 1
    
    if report_type == "On-Site Service":
        return 1

    return False

def get_amount_of_hours(begin, end, report_doc):
    if type(begin) == str:
        begin = datetime.fromisoformat(str(begin))
    if type(end) == str:
        end = datetime.fromisoformat(str(end))
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
    print("######", description)
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
                                                "item_code": item.item_code,
                                                "description": item.item_name,
                                                "qty": item.qty
                                                })
        delivery_note_items.append(delivery_note_item)
    return delivery_note_items

def create_delivery_note_items(items):
    pass

@frappe.whitelist()
def create_delivery_note(service_report):
    report_doc = frappe.get_doc("Service Report", service_report)
    if not report_doc.delivery_note:
        items = []

        if(len(report_doc.work) > 0):
            items = items + get_items_from_sr_work(report_doc.work, report_doc)
        if(len(report_doc.items) > 0):
            items = items + get_items_from_sr_items(report_doc.items)
        
        print("items vorher------")
        for item in report_doc.items:
            print(item.item_code, item.name, item.qty)


        if len(items) > 0:
            delivery_note_doc = frappe.get_doc({"doctype": "Delivery Note",
                                                "title": "Lieferschein zu " + report_doc.name,
                                                "customer": report_doc.customer,
                                                "status": "Draft",
                                                "company": frappe.get_doc("Global Defaults").default_company,
                                                "delivery_note_introduction_text": "Lieferschein zu Serviceprotokoll " + report_doc.name,
                                                })
            print(delivery_note_doc.customer)
            
            print("items zu dn------")
            for item in items:
                delivery_note_doc.append("items", item)
                print(item.item_code, item.name, item.qty)


            
            #debug
            print("items nachher------")
            for item in delivery_note_doc.items:
                print(item.item_code, item.name, item.qty)

            DN = frappe.get_doc("Delivery Note", delivery_note_doc.insert().name)
            report_doc.delivery_note = DN.name
            report_doc.status = "Delivered"
            report_doc.save()
            frappe.msgprint("Lieferschein <a href=\"/app/delivery-note/" + DN.name + "\">" + DN.name + "</a> erstellt.")
                
        else:
            frappe.throw('Keine abrechenbaren Positionen vorhanden.')
    else:
        frappe.msgprint("Lieferschein <a href=\"/app/delivery-note/" + report_doc.delivery_note + "\">" + report_doc.delivery_note + "</a> bereits vorhanden.")
                                        
def validate_work_duration(report_doc):
    settings = frappe.get_single("Fieldservice Settings")
    for work_position in report_doc.work:
        qty = get_amount_of_hours(work_position.begin, work_position.end, report_doc)
        if qty > settings.max_work_duration:
            print(work_position.idx)
            frappe.throw("Work duration longer then expected.<br>Work Item No.: " + str(work_position.idx) + "<br>" + str(work_position.description))

def validate_empty_work_description(report_doc):
    for work_position in report_doc.work:
        print("validate")
        print(work_position.description)
        if not work_position.description:
            frappe.throw("Work description empty.<br>Work Item No.: " + str(work_position.idx))
        if len(work_position.description) < 4:
            frappe.throw("Work description too short.<br>Work Item No.: " + str(work_position.idx))

def validate_start_before_end(report_doc):
    for work_position in report_doc.work:
        if work_position.begin == work_position.end:
            frappe.throw("Work times are equal, check begin and end.<br>Work Item No.: " + str(work_position.idx))
        if work_position.begin > work_position.end:
            frappe.throw("Work beginn is after end, check begin and end.<br>Work Item No.: " + str(work_position.idx))





    
    
