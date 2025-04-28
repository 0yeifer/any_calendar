# Copyright (c) 2025, Yeifer and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import Contact
import requests

class CustomContact(Contact):
    def after_insert(self):
        if self.custom_calendar_provider == "Calendar Hubspot":
            try:
                if not self.custom_calendar:
                    frappe.log_error("Custom calendar no especificado", "CustomContact.after_insert")
                    return
                hubspot = frappe.get_doc("Calendar Hubspot", self.custom_calendar)
                access_token = hubspot.get("access_token")
                calendar_id = hubspot.get("calendar_id")

                # Check if the contact already exists in HubSpot
                contact_exists = validate_contact_in_hubspot(self, access_token, calendar_id)
                if contact_exists:
                    frappe.log_error("El contacto ya existe en HubSpot", "CustomContact.after_insert")
                    return
                # Create the contact in HubSpot
                create_hubspot_contact(
                    firstname = self.first_name,
                    calendar_id = calendar_id,
                    access_token = access_token,
                    phone = self.mobile_no,
                )
                print("\n\n")
                print("Contact created in HubSpot")
                print("\n\n")

            except frappe.ValidationError as ve:
                frappe.log_error(f"Error de validación: {str(ve)}", "CustomContact.after_insert")
            except frappe.PermissionError as pe:
                frappe.log_error(f"Error de permisos: {str(pe)}", "CustomContact.after_insert")
            except Exception as e:
                frappe.log_error(f"Error al crear contacto en Hubspot: {str(e)}", "CustomContact.after_insert")
                raise


def create_hubspot_contact(firstname, phone, calendar_id, access_token):
    url = "https://api.hubapi.com/crm/v3/objects/CONTACTS"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "properties": {
            "firstname": firstname,
            "phone": f"+57{phone}",
            "hubspot_owner_id": calendar_id,
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to create contact: {str(e)}"}
    
def validate_contact_in_hubspot(self, access_token, calendar_id):
    url = "https://api.hubapi.com/crm/v3/objects/CONTACTS"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    params = {
        "properties": ["firstname", "phone"],
        "hubspot_owner_id": calendar_id,
        "archived": False
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            for contact in data["results"]:
                if contact["properties"]["firstname"] == self.first_name and contact["properties"]["phone"] == f"+{self.mobile_no}":
                    return True
        return False
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to validate contact: {str(e)}"}

