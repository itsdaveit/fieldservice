# Copyright (c) 2022, itsdve GmbH and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class FieldserviceSettings(Document):
	pass

@frappe.whitelist()
def fetch_ai_models():
	"""Fetch available models from Anthropic API."""
	import anthropic

	settings = frappe.get_single('Fieldservice Settings')
	api_key = settings.get_password('ai_api_key')
	if not api_key:
		frappe.throw('Kein API Key hinterlegt.')

	client = anthropic.Anthropic(api_key=api_key)
	models = client.models.list(limit=50)

	return [{'id': m.id, 'name': m.display_name} for m in models.data]

@frappe.whitelist()
def get_default_prompt():
	"""Return the default AI system prompt."""
	from fieldservice.review_pipeline import DEFAULT_AI_SYSTEM_PROMPT
	return DEFAULT_AI_SYSTEM_PROMPT
