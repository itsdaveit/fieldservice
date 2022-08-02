# -*- coding: utf-8 -*-
# Copyright (c) 2019, itsdve GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
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

		
