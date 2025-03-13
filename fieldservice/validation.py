# -*- coding: utf-8 -*-
# Copyright (c) 2023, itsdve GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from fieldservice.api import get_amount_of_hours

def check_work_duration(report_doc):
    """Check work duration and return error messages instead of throwing errors"""
    errors = []
    settings = frappe.get_single("Fieldservice Settings")
    for work_position in report_doc.work:
        if not work_position.begin or not work_position.end:
            errors.append(_("One Datetime is missing. Work Item No.: {}").format(str(work_position.idx)))
        else:
            qty = get_amount_of_hours(work_position.begin, work_position.end)
            if qty > settings.max_work_duration:
                errors.append(_("Work duration longer then expected. Work Item No.: {}").format(str(work_position.idx)))
    return errors

def check_empty_work_description(report_doc):
    """Check work description and return error messages instead of throwing errors"""
    errors = []
    for work_position in report_doc.work:
        if not work_position.description:
            errors.append(_("Work description empty. Work Item No.: {}").format(str(work_position.idx)))
        elif len(work_position.description) < 4:
            errors.append(_("Work description too short. Work Item No.: {}").format(str(work_position.idx)))
    return errors

def check_start_before_end(report_doc):
    """Check start before end and return error messages instead of throwing errors"""
    errors = []
    for work_position in report_doc.work:
        if work_position.begin and work_position.end:
            if work_position.begin == work_position.end:
                errors.append(_("Work times are equal. Check begin and end. Work Item No.: {}").format(str(work_position.idx)))
            if work_position.begin > work_position.end:
                errors.append(_("Work begin is after end. Check begin and end. Work Item No.: {}").format(str(work_position.idx)))
    return errors

def check_work_items(report_doc):
    """Check if work items exist and return error messages instead of throwing errors"""
    errors = []
    if not report_doc.work:
        errors.append(_("No work items found."))
    return errors

def check_empty_work_item_address(report_doc):
    """Check work item address and return error messages instead of throwing errors"""
    errors = []
    for work_position in report_doc.work:
        if work_position.service_type == "On-Site Service" and work_position.travel_charges == 1 and not work_position.address:
            errors.append(_("No work item address found. Work Item No.: {}").format(str(work_position.idx)))
    return errors

def validate_service_report(report_doc, throw_errors=False):
    """
    Validate service report and either return error messages or throw errors
    
    Args:
        report_doc: Service Report document
        throw_errors: If True, throw errors instead of returning them
        
    Returns:
        List of error messages if throw_errors is False, otherwise throws the first error
    """
    all_errors = []
    
    # Check work duration
    errors = check_work_duration(report_doc)
    if errors and throw_errors:
        frappe.throw(errors[0])
    all_errors.extend(errors)
    
    # Check work description
    errors = check_empty_work_description(report_doc)
    if errors and throw_errors:
        frappe.throw(errors[0])
    all_errors.extend(errors)
    
    # Check start before end
    errors = check_start_before_end(report_doc)
    if errors and throw_errors:
        frappe.throw(errors[0])
    all_errors.extend(errors)
    
    # Check work items
    errors = check_work_items(report_doc)
    if errors and throw_errors:
        frappe.throw(errors[0])
    all_errors.extend(errors)
    
    # Check work item address
    errors = check_empty_work_item_address(report_doc)
    if errors and throw_errors:
        frappe.throw(errors[0])
    all_errors.extend(errors)
    
    return all_errors 