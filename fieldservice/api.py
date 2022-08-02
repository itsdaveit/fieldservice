from __future__ import unicode_literals

import json
from time import strftime, strptime
import frappe
import frappe.handler
import frappe.client
from datetime import datetime, date, timedelta

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

def get_surcharge_item_description(item_code,description, begin, end):

    surcharge_item_doc = frappe.get_doc("Item", item_code)
    item_description = surcharge_item_doc.description + "<br>" + begin.strftime("%d.%m.%Y %H:%M") + " - " + end.strftime("%d.%m.%Y %H:%M") + " Uhr"
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
        print(item)
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
def get_item_from_surcharge_in_percent(report_doc):
    delivery_note_items = []
    surcharge_dict = get_surcharge(report_doc)
    for el in surcharge_dict:
        if el.surcharge_in_percent != "0" and el.surcharge_in_percent != "None":
            print(el.surcharge_in_percent)
            surcharge_item = frappe.get_all("Item", filters = {"item_name": "Arbeiten außerhalb der Arbeitszeit, Zuschlag"}, fields = ["item_code", "item_name"])
            print(surcharge_item)
            a = surcharge_item[0]["item_name"] +": " + el.surcharge_in_percent + "%"
            # print(surcharge_item.item_code)
            # print(surcharge_item.item_name)
            delivery_note_item = frappe.get_doc({"doctype": "Delivery Note Item",
                                                "item_code": surcharge_item[0]["item_code"],
                                                "description":a,
                                                "qty": el.qty,
                                                "rate": float(el.work_item_price)*float(el.surcharge_in_percent)/100
                                                })
            print(delivery_note_item.description)
            delivery_note_item.description = get_surcharge_item_description(surcharge_item[0]["item_code"],a, el.begin, el.end)
            delivery_note_items.append(delivery_note_item)
    return delivery_note_items
def get_item_from_sur_per_hour(report_doc):
    delivery_note_items = []
    surcharge_dict = get_surcharge(report_doc)
    for el in surcharge_dict:   

        if el.surcharge_per_hour != '0'and el.surcharge_per_hour != '' and el.surcharge_per_hour != 0:
            print(el.surcharge_per_hour)
            surcharge_item = frappe.get_all("Item", filters = {"item_name": "Arbeiten außerhalb der regulären Arbeitszeit, Zuschlag pro Stunde"}, fields = ["item_code", "item_name"])
            print(surcharge_item)
            a = surcharge_item[0]["item_name"] +": " + str(el.surcharge_per_hour) + " Euro"
            # print(surcharge_item.item_code)
            # print(surcharge_item.item_name)
            delivery_note_item = frappe.get_doc({"doctype": "Delivery Note Item",
                                                "item_code": surcharge_item[0]["item_code"],
                                                "description":a,
                                                "qty": el.qty,
                                                "rate": el.surcharge_per_hour 

                                                })
            print(delivery_note_item.description)
            delivery_note_item.description = get_surcharge_item_description(surcharge_item[0]["item_code"],a, el.begin, el.end)
            delivery_note_items.append(delivery_note_item)
    return delivery_note_items
def get_item_from_sur_per_assignment(report_doc):
    delivery_note_items = []
    surcharge_dict = get_surcharge(report_doc)
    for el in surcharge_dict:   

        if el.surcharge_per_assignment != '0'and el.surcharge_per_assignment != '' and el.surcharge_per_assignment != 0:
            print(el.surcharge_per_assignment)
            surcharge_item = frappe.get_all("Item", filters = {"item_name": "Arbeiten außerhalb der regulären Arbeitszeit, Zuschlag pro Einsatz"}, fields = ["item_code", "item_name"])
            print("surcharge_item")
            print(surcharge_item)
    
        
            a =surcharge_item[0]["item_name"] +": " + str(el.surcharge_per_assignment) + " Euro"
            # print(surcharge_item.item_code)
            # print(surcharge_item.item_name)
            delivery_note_item = frappe.get_doc({"doctype": "Delivery Note Item",
                                                "item_code": surcharge_item[0]["item_code"],
                                                "description":a,
                                                "qty": 1,
                                                "rate": el.surcharge_per_assignment 

                                                })
            print(delivery_note_item.description)
            delivery_note_item.description = get_surcharge_item_description(surcharge_item[0]["item_code"],a, el.begin, el.end)
            delivery_note_items.append(delivery_note_item)
            break
    return delivery_note_items
        
def create_delivery_note_items(items):
    pass

@frappe.whitelist()
def create_delivery_note(service_report):
    
    report_doc = frappe.get_doc("Service Report", service_report)
    a = get_surcharge(report_doc)
    #b= get_item_from_surcharge(report_doc)

    if not report_doc.delivery_note:
        items = []

        if(len(report_doc.work) > 0):
            items = items + get_items_from_sr_work(report_doc.work, report_doc)
        if(len(report_doc.items) > 0):
            items = items + get_items_from_sr_items(report_doc.items)
        if len(get_item_from_surcharge_in_percent(report_doc)) > 0:
            items = items + get_item_from_surcharge_in_percent(report_doc)
        if len(get_item_from_sur_per_hour(report_doc)) > 0:
            items = items + get_item_from_sur_per_hour(report_doc)
        if len(get_item_from_sur_per_assignment(report_doc)) > 0:
            items = items + get_item_from_sur_per_assignment(report_doc)
           
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
        if not work_position.begin or not work_position.end:
            frappe.throw("One Datetime is missing.<br>Work Item No.: " + str(work_position.idx))
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

def validate_work_items(report_doc):
    if not report_doc.work:
        frappe.throw("No work items found.")

def get_datetime_from_timedelta(time_delta_list,date_string):
    s_l_date =[]
    for x in time_delta_list:
        x_date = x.from_time
        s_l_d_st = date_string + " " + str(x_date)
        s_l_d_dt = datetime.strptime(s_l_d_st, '%d.%m.%Y %H:%M:%S')
        x.update({"from_time" : s_l_d_dt})
        s_l_date.append(x)
        print(s_l_date)
    return s_l_date

def get_work_end(sorted_time_list,prev_el_s_l,s_l_date,work_item_price,report_doc):
   
    surcharge_dict_list = []
    for el in sorted_time_list: 
        if el == min(sorted_time_list):
            prev_el_s_l = prev_el_s_l
        else:
            prev_el_s_l = el
        index_prev_el = next((i for i, x in enumerate(s_l_date) if x["from_time"] == prev_el_s_l), None)
        n_el = sorted_time_list[sorted_time_list.index(el)+1]
        # print('element')
        # print(el)
        # print('prev_el_s_l:') 
        # print(prev_el_s_l)
        # print("n_el")
        # print(n_el)
        surcharge_dict = s_l_date[index_prev_el]
        qty = get_amount_of_hours(el, n_el, report_doc)
        surcharge_dict["qty"] = qty
        surcharge_dict["begin"] = el
        surcharge_dict["end"] = n_el
        surcharge_dict["work_item_price"]= work_item_price
        surcharge_dict_list.append(surcharge_dict)
        if n_el == max(sorted_time_list):
            break
    print('####****####')
    print(surcharge_dict_list)
    
    return surcharge_dict_list
def get_surcharge(report_doc):
    employee_item = frappe.get_all('Employee Item Assignment', 
                                    filters={'employee': report_doc.employee,
                                            'service_type': report_doc.report_type},
                                    fields={'name', 'item'}
                                    )
    item_code = employee_item[0].item
    item_price_li = frappe.get_all("Item Price", 
                                    filters = {"item_code": item_code},
                                    fields = "price_list_rate"
                                    )
    work_price = item_price_li[0].price_list_rate
    
    customer = report_doc.customer
    rules = frappe.get_all("Pricing Rule", 
                            filters = {"customer":customer,
                                        "item_group" :["in",["Dienstleistungen", "Arbeitszeiten Techniker"]] },
                             fields = "rate"
                             )
    if len(rules) > 0:
        work_item_price = rules[0]["rate"]
    else:
        work_item_price = work_price

    cust_surch = frappe.get_all("Service Report Surcharge", filters={"customer":customer})
    print(customer)
    # if len(cust_surch) == 0:
    surcharge_dict_list = []
    for work_position in report_doc.work:
        
        date_begin = work_position.begin.date()
        date_string = date_begin.strftime('%d.%m.%Y')
        date_end = work_position.end.date()
        date_end_string = date_end.strftime('%d.%m.%Y')
        weekday_begin = work_position.begin.strftime('%A')
        prev_day = date_begin - timedelta(days=1)
        work_begin = work_position.begin
        work_end = work_position.end
        
        fields = ["from_time", "surcharge_in_percent", "surcharge_per_hour","surcharge_per_assignment"]
        holiday_list = [x.date for x in frappe.get_all("Public holiday",fields = "date")]
        print(holiday_list)
        sur_day_list = [prev_day,date_begin]
        if date_begin != date_end:
            sur_day_list.append(date_end)
        print('####sur_day_list#####')
        print(sur_day_list)
        s_l_date = []
        if len(cust_surch) == 0:
            for el in sur_day_list:
                if el in holiday_list:
                    surcharge_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": "Public holiday"}, fields = fields)
                else:
                    surcharge_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": el.strftime('%A') }, fields = fields )
                s_l_date_day = get_datetime_from_timedelta(surcharge_list,el.strftime('%d.%m.%Y') )
                s_l_date += s_l_date_day
        else:
            for el in holiday_list:
                if el in holiday_list:
                    surcharge_cust_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": "Public holiday", "customer":customer}, fields = fields)
                    if len(surcharge_cust_list) > 0:
                        surcharge_list = surcharge_cust_list
                    else:    
                        surcharge_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": "Public holiday"}, fields = fields)
                else:
                    surcharge_cust_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": el.strftime('%A'), "customer":customer}, fields = fields)
                    if len(surcharge_cust_list) > 0:
                        surcharge_list = surcharge_cust_list
                    else:
                        surcharge_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": el.strftime('%A') }, fields = fields )
                    s_l_date_day = get_datetime_from_timedelta(surcharge_list,el.strftime('%d.%m.%Y') )
                    s_l_date += s_l_date_day
            # if prev_day in holiday_list:
            #     surcharge_list_prev_day = frappe.get_all("Service Report Surcharge", filters= {"weekday": "Public holiday"}, fields = fields)
            # else:
            #     surcharge_list_prev_day = frappe.get_all("Service Report Surcharge", filters= {"weekday": prev_day.strftime('%A') }, fields = fields )
            # s_l_date_prev_day = get_datetime_from_timedelta(surcharge_list_prev_day,prev_day.strftime('%d.%m.%Y') )
            # if  date_begin in holiday_list:
            #     surcharge_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": "Public holiday"}, fields = fields)  
            # else:
            #     surcharge_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": weekday_begin}, fields = fields )
            # s_l_date_begin = get_datetime_from_timedelta(surcharge_list,date_string)
            # s_l_date_begin += s_l_date_prev_day
            # if date_begin != date_end:
            #     if date_end in holiday_list:
            #         surcharge_list_end_date =surcharge_list = frappe.get_all("Service Report Surcharge", filters= {"weekday": "Public holiday"}, fields = fields)  
            #     else:    
            #         surcharge_list_end_date = frappe.get_all("Service Report Surcharge", filters= {"weekday": work_position.end.strftime('%A')}, fields = fields )
            #     s_l_date_end = get_datetime_from_timedelta(surcharge_list_end_date,date_end_string)
            # else:
            #     s_l_date_end = []
        # else:
        #     if prev_day in holiday_list:
        #         surcharge_cust_list_prev_day = frappe.get_all("Service Report Surcharge", filters= {"weekday": "Public holiday", "customer":customer}, fields = fields)
        #         if len(surcharge_cust_list_prev_day) > 0:
        #             surcharge_list_prev_day = surcharge_cust_list_prev_day
        #         else:    
        #             surcharge_list_prev_day = frappe.get_all("Service Report Surcharge", filters= {"weekday": "Public holiday"}, fields = fields)
        #     else:
        #         surcharge_cust_list_prev_day = frappe.get_all("Service Report Surcharge", filters= {"weekday": prev_day.strftime('%A'), "customer":customer}, fields = fields)
        #         if len(surcharge_cust_list_prev_day) > 0:
        #             surcharge_list_prev_day = surcharge_cust_list_prev_day
        #         else:
        #             surcharge_list_prev_day = frappe.get_all("Service Report Surcharge", filters= {"weekday": prev_day.strftime('%A') }, fields = fields )
        #     s_l_date_prev_day = get_datetime_from_timedelta(surcharge_list_prev_day,prev_day.strftime('%d.%m.%Y') )
        #     if  date_begin in holiday_list:
        #         surcharge_cust_list = frappe.get_all("Service Report Surcharge", 
        #                                             filters= {"weekday": "Public holiday", "customer":customer}, fields = fields)
        #         if len(surcharge_cust_list) > 0:
        #             surcharge_list = surcharge_cust_list
        #         else:
        #             surcharge_list = frappe.get_all("Service Report Surcharge", 
        #                                             filters= {"weekday": "Public holiday"}, fields = fields)  
        #     else:
        #         surcharge_cust_list = frappe.get_all("Service Report Surcharge", 
        #                                             filters= {"weekday": weekday_begin, "customer":customer}, fields = fields )
        #         if len(surcharge_cust_list) > 0:
        #             surcharge_list = surcharge_cust_list  
        #         else:
        #             surcharge_list = frappe.get_all("Service Report Surcharge", 
        #                                             filters= {"weekday": weekday_begin}, fields = fields)    
        #     s_l_date_begin = get_datetime_from_timedelta(surcharge_list,date_string)
        #     s_l_date_begin += s_l_date_prev_day
        #     if date_begin != date_end:
        #         if date_end in holiday_list:
        #             surcharge_cust_list_end_date = frappe.get_all("Service Report Surcharge", 
        #                                             filters= {"weekday": "Public holiday", "customer":customer}, fields = fields)
        #             if len(surcharge_cust_list_end_date) > 0:
        #                 surcharge_list_end_date = surcharge_cust_list_end_date
        #             else:
        #                 surcharge_list_end_date =surcharge_list = frappe.get_all("Service Report Surcharge", 
        #                                             filters= {"weekday": "Public holiday"}, fields = fields)  
        #         else:
        #             surcharge_cust_list_end_date = frappe.get_all("Service Report Surcharge", 
        #                                             filters= {"weekday": work_position.end.strftime('%A'), "customer":customer}, fields = fields )    
        #             if len(surcharge_cust_list_end_date) > 0:
        #                 surcharge_list_end_date = surcharge_cust_list_end_date
        #             else:
        #                 surcharge_list_end_date = frappe.get_all("Service Report Surcharge", 
        #                                             filters= {"weekday": work_position.end.strftime('%A')}, fields = fields )
        #         s_l_date_end = get_datetime_from_timedelta(surcharge_list_end_date,date_end_string)
        #     else:
        #         s_l_date_end = []


        #s_l_date = s_l_date_begin + s_l_date_end
        sur_li =[x.from_time for x in s_l_date]
        sorted_sur_li =sorted(sur_li)
        time_list = [work_begin,work_end]
        for element in s_l_date:
            if element.from_time > work_begin and element.from_time < work_end: 
                time_list.append(element.from_time)       
        sorted_time_list = sorted(time_list)
        res = [x for x in sorted_sur_li if x < work_begin ]
        if work_begin in sur_li:
            prev_el_s_l = work_begin
        else:
            prev_el_s_l = max(res)
           
        
        print(sorted_time_list)
        surcharge_dict = get_work_end(sorted_time_list,prev_el_s_l,s_l_date,work_item_price,report_doc)
        surcharge_dict_list += surcharge_dict
                
        print('#######list#####') 
        print('#######neue Liste#####') 
        
    print(surcharge_dict_list)  
    return surcharge_dict_list        