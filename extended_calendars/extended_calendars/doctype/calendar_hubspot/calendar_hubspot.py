# Copyright (c) 2025, Yeifer and contributors
# For license information, please see license.txt

import frappe
import json
import time
from frappe.model.document import Document
import requests
from datetime import datetime, timedelta
from frappe.utils import get_datetime

class CalendarHubspot(Document):
    def validate(self):
        """Validate required fields before saving the document."""
        print(f"Validating: usser={self.usser}, access_token={self.access_token}, calendar_id={self.calendar_id}")
        if not self.usser:
            frappe.throw("Please enter an email in the 'Usser' field.")
        if not self.access_token:
            frappe.throw("Please enter the access token in 'Access Token' field.")
        if not self.calendar_id:
            frappe.throw("Please enter the calendar ID in 'Calendar ID' field.")
        # owner_id es opcional
        print(f"Owner ID (optional): {getattr(self, 'owner_id', 'Not set')}")
        print("Validation passed successfully.")

    def get_access_token(self):
        """Retrieve the HubSpot access token."""
        if not self.access_token:
            frappe.throw("No token has been entered in 'Access Token'.")
        return self.access_token

@frappe.whitelist()
def get_hubspot_contact_id_by_email(email, access_token, headers):
    """Fetch HubSpot contact ID by email using the HubSpot API."""
    print(f"Fetching HubSpot contact ID for email: {email}")
    
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    payload = {
        "properties": ["email"],
        "filterGroups": [{
            "filters": [{
                "propertyName": "email",
                "operator": "EQ",
                "value": email
            }]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"API response for email {email}: {response.status_code}, {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                contact_id = results[0].get("id")
                print(f"Found contact ID {contact_id} for email {email}")
                return contact_id
            else:
                print(f"No contact found for email {email}")
                return None
        else:
            error_msg = f"Error fetching contact for {email}: {response.status_code} - {response.text}"
            print(error_msg)
            frappe.log_error(error_msg, "HubSpot Contact Fetch Error")
            return None
    except Exception as e:
        error_msg = f"Exception fetching contact for {email}: {str(e)}"
        print(error_msg)
        frappe.log_error(error_msg, "HubSpot Contact Fetch Exception")
        return None

@frappe.whitelist()
def create_hubspot_contact(email, first_name, last_name, owner_id, access_token, headers):
    """Create a new contact in HubSpot if it doesn't exist."""
    print(f"Creating new HubSpot contact for email: {email}")
    
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    payload = {
        "properties": {
            "email": email,
            "firstname": first_name if first_name else "X",
            "lastname": last_name if last_name else "X"
        }
    }
    if owner_id:  # Solo agregar hubspot_owner_id si está presente
        payload["properties"]["hubspot_owner_id"] = owner_id
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Create contact API response: {response.status_code}, {response.text}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            contact_id = data.get("id")
            print(f"Successfully created contact with ID {contact_id} for email {email}")
            return contact_id
        else:
            error_msg = f"Error creating contact for {email}: {response.status_code} - {response.text}"
            print(error_msg)
            frappe.log_error(error_msg, "HubSpot Contact Creation Error")
            return None
    except Exception as e:
        error_msg = f"Exception creating contact for {email}: {str(e)}"
        print(error_msg)
        frappe.log_error(error_msg, "HubSpot Contact Creation Exception")
        return None

@frappe.whitelist()
def get_or_create_frappe_contact(email, first_name, last_name):
    """Get or create a Contact in Frappe based on email."""
    contact_name = frappe.db.get_value("Contact", {"email_id": email}, "name")
    if contact_name:
        print(f"Found existing Contact for email {email}: {contact_name}")
        return contact_name
    
    # Crear nuevo contacto si no existe
    contact = frappe.get_doc({
        "doctype": "Contact",
        "email_ids": [{"email_id": email, "is_primary": 1}],
        "first_name": first_name or "Unknown",
        "last_name": last_name or ""
    })
    contact.insert(ignore_permissions=True)
    print(f"Created new Contact for email {email}: {contact.name}")
    return contact.name


@frappe.whitelist()
def pull_hubspot_data(hubspot_doc):
    """Fetch meeting data from HubSpot and create/update events in Frappe's Event Doctype."""
    print(f"Executing pull_hubspot_data for doc: {hubspot_doc}")
    doc = frappe.get_doc("Calendar Hubspot", hubspot_doc)
    
    if not doc.pull:
        print("Pull is disabled.")
        return {"success": False, "message": "Pull is disabled."}
    
    access_token = doc.get_access_token()
    calendar_id = doc.calendar_id  # Usamos el calendar_id del documento
    print(f"Using access token: {access_token}, Calendar ID: {calendar_id}")
    
    base_url = "https://api.hubapi.com/crm/v3/objects/meetings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    params = {
        "properties": "hs_meeting_title,hs_meeting_start_time,hs_meeting_end_time,hs_meeting_body",
        "limit": "100"
    }

    all_meetings = []
    next_page = None
    page_count = 0
    total_meetings = 0
    created_count = 0
    updated_count = 0

    try:
        while True:
            page_count += 1
            current_params = params.copy()
            if next_page:
                current_params["after"] = next_page

            print(f"Fetching page {page_count} of meetings...")
            response = requests.get(base_url, headers=headers, params=current_params)
            
            if response.status_code != 200:
                error_msg = f"Error fetching meetings: {response.status_code} - {response.text}"
                print(error_msg)
                frappe.throw(error_msg)

            data = response.json()
            meetings = data.get("results", [])
            total_meetings += len(meetings)
            print(f"Found {len(meetings)} meetings in this batch (Total: {total_meetings})")

            for meeting in meetings:
                meeting_id = meeting.get("id")
                if not meeting_id:
                    print("Skipping meeting: No ID found.")
                    continue

                # Verificar si el evento ya existe en Frappe por custom_calendar_event_id
                event_name = frappe.db.get_value(
                    "Event",
                    {"custom_calendar_event_id": meeting_id},
                    "name"
                )
                print(f"Checking event with meeting_id {meeting_id}: Found event_name = {event_name}")
                
                # Obtener propiedades de la reunión
                properties = meeting.get("properties", {})
                subject = properties.get("hs_meeting_title", "Reunión")
                start_time_str = properties.get("hs_meeting_start_time", "1970-01-01T00:00:00Z")
                end_time_str = properties.get("hs_meeting_end_time", "1970-01-01T00:00:00Z")
                
                # Parsear las fechas ISO 8601 y formatearlas para Frappe
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                start_time_formatted = start_time.strftime("%Y-%m-%d %H:%M:%S")
                end_time_formatted = end_time.strftime("%Y-%m-%d %H:%M:%S")
                description = properties.get("hs_meeting_body", "")

                # Obtener participantes
                associations_url = f"{base_url}/{meeting_id}/associations/contact"
                assoc_response = requests.get(associations_url, headers=headers)
                participants = []
                if assoc_response.status_code == 200:
                    assoc_data = assoc_response.json()
                    for result in assoc_data.get("results", []):
                        contact_id = result.get("id")
                        if contact_id:
                            contact_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
                            contact_response = requests.get(
                                contact_url,
                                headers=headers,
                                params={"properties": "firstname,lastname,email"}
                            )
                            if contact_response.status_code == 200:
                                contact_data = contact_response.json()
                                contact_props = contact_data.get("properties", {})
                                participants.append({
                                    "email": contact_props.get("email"),
                                    "first_name": contact_props.get("firstname"),
                                    "last_name": contact_props.get("lastname")
                                })
                else:
                    print(f"Failed to fetch associations for meeting {meeting_id}: {assoc_response.status_code} - {assoc_response.text}")

                # Preparar datos del evento con nombres de campos correctos
                event_data = {
                    "subject": subject,
                    "starts_on": start_time_formatted,
                    "ends_on": end_time_formatted,
                    "description": description,
                    "custom_calendar_event_id": meeting_id,  # El meeting_id de HubSpot
                    "custom_calendar_provider": "Calendar Hubspot",
                    "custom_hubspot_calendar_id": calendar_id,  # El calendar_id de HubSpot
                    "custom_pulled_from_calendar_provider": 1,
                    "custom_calendar": hubspot_doc  # Asignamos el name del documento Calendar Hubspot
                }
                print(f"Event data prepared for meeting_id {meeting_id}: {json.dumps(event_data, indent=2)}")

                # Manejar participantes
                event_participants = []
                for participant in participants:
                    if participant.get("email"):
                        contact_name = get_or_create_frappe_contact(
                            participant["email"],
                            participant["first_name"],
                            participant["last_name"]
                        )
                        event_participants.append({
                            "reference_doctype": "Contact",
                            "reference_docname": contact_name
                        })
                print(f"Participants for meeting_id {meeting_id}: {len(event_participants)}")

                if event_name:
                    # Actualizar evento existente
                    print(f"Updating existing event {event_name} with meeting_id {meeting_id} and calendar_id {calendar_id}...")
                    event = frappe.get_doc("Event", event_name)
                    event.update(event_data)
                    event.save(ignore_permissions=True)
                    # Actualizar participantes
                    event.set("event_participants", event_participants)
                    event.save(ignore_permissions=True)
                    updated_count += 1
                    print(f"Updated event {event_name} with meeting_id {meeting_id}")
                    # Verificar campos después de actualizar
                    updated_event = frappe.get_doc("Event", event_name)
                    print(f"Post-update: custom_calendar_event_id={updated_event.custom_calendar_event_id}, "
                          f"custom_calendar_provider={updated_event.custom_calendar_provider}, "
                          f"custom_hubspot_calendar_id={updated_event.custom_hubspot_calendar_id}, "
                          f"custom_pulled_from_calendar_provider={updated_event.custom_pulled_from_calendar_provider}, "
                          f"custom_calendar={updated_event.custom_calendar}")
                else:
                    # Crear nuevo evento
                    print(f"Creating new event for meeting_id {meeting_id} with calendar_id {calendar_id}...")
                    event = frappe.get_doc({
                        "doctype": "Event",
                        **event_data,
                        "event_participants": event_participants
                    })
                    event.insert(ignore_permissions=True)
                    created_count += 1
                    print(f"Created new event {event.name} with meeting_id {meeting_id}")
                    # Verificar campos después de crear
                    print(f"Post-create: custom_calendar_event_id={event.custom_calendar_event_id}, "
                          f"custom_calendar_provider={event.custom_calendar_provider}, "
                          f"custom_hubspot_calendar_id={event.custom_hubspot_calendar_id}, "
                          f"custom_pulled_from_calendar_provider={event.custom_pulled_from_calendar_provider}, "
                          f"custom_calendar={event.custom_calendar}")

                all_meetings.append(meeting)
                time.sleep(0.1)

            if "paging" in data and "next" in data["paging"]:
                next_page = data["paging"]["next"]["after"]
            else:
                break

        result = {
            "total_meetings": total_meetings,
            "page_count": page_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "meetings": all_meetings
        }
        
        print("\nHubSpot Meetings Data Processed:")
        print(f"Total meetings fetched: {total_meetings} from {page_count} pages")
        print(f"Events created: {created_count}, Events updated: {updated_count}")
        print(json.dumps(result, indent=2))

        return {
            "success": True,
            "message": f"Processed {total_meetings} meetings: {created_count} created, {updated_count} updated",
            "data": result
        }

    except Exception as e:
        error_msg = f"Pull error: {str(e)}"
        print(error_msg)
        frappe.log_error(error_msg, "HubSpot Pull Error")
        return {
            "success": False,
            "message": error_msg
        }



@frappe.whitelist()
def push_hubspot_meeting(event, access_token, headers, owner_id=None):
    """Push a new meeting to HubSpot and update the event with the new meeting ID."""
    print(f"Pushing new meeting for event {event.name}")
    
    participants = frappe.get_all(
        "Event Participants",
        filters={"parent": event.name},
        fields=["reference_doctype", "reference_docname"]
    )
    
    print(f"Event {event.name} - Number of participants found: {len(participants)}")
    
    start_time = get_datetime(event.starts_on)
    end_time = get_datetime(event.ends_on) if event.ends_on else (start_time + timedelta(minutes=30))
    start_timestamp = int(start_time.timestamp() * 1000)
    end_timestamp = int(end_time.timestamp() * 1000)
    
    contact_ids = []
    if participants:
        for participant in participants:
            print(f"Processing participant for event {event.name}: {participant}")
            if participant.reference_doctype == "Contact":
                try:
                    contact = frappe.get_doc("Contact", participant.reference_docname)
                    email = contact.email_id
                    first_name = contact.first_name
                    last_name = contact.last_name
                    print(f"Event {event.name} - Participant Contact:")
                    print(f"  Email: {email if email else 'Not set'}")
                    print(f"  First Name: {first_name if first_name else 'Not set'}")
                    print(f"  Last Name: {last_name if last_name else 'Not set'}")
                    
                    if email:
                        contact_id = get_hubspot_contact_id_by_email(email, access_token, headers)
                        if contact_id:
                            contact_ids.append(contact_id)
                        else:
                            contact_id = create_hubspot_contact(email, first_name, last_name, owner_id, access_token, headers)
                            if contact_id:
                                contact_ids.append(contact_id)
                            else:
                                print(f"Warning: Failed to create HubSpot contact for email {email}")
                    else:
                        print(f"Warning: No email found for Contact {participant.reference_docname}")
                except frappe.DoesNotExistError:
                    print(f"Error: Contact {participant.reference_docname} not found for event {event.name}")
            else:
                print(f"Participant for event {event.name} is not a Contact: {participant.reference_doctype}")
    else:
        print(f"No participants found for event {event.name}.")
    
    if not contact_ids:
        print(f"Skipping event {event.name}: No valid HubSpot contact IDs found.")
        return False, f"Skipping event {event.name}: No valid HubSpot contact IDs found."
    
    meeting_data = {
        "properties": {
            "hs_meeting_title": event.subject or "Reunión",
            "hs_meeting_start_time": start_timestamp,
            "hs_meeting_end_time": end_timestamp,
            "hs_meeting_body": event.description or "",
            "hs_timestamp": start_timestamp
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": 200
                    }
                ]
            } for contact_id in contact_ids
        ]
    }
    if owner_id:  # Solo agregar hubspot_owner_id si está presente
        meeting_data["properties"]["hubspot_owner_id"] = owner_id
    
    url = "https://api.hubapi.com/crm/v3/objects/meetings"
    print(f"Pushing new meeting to HubSpot: {event.name}")
    print(f"Meeting data: {json.dumps(meeting_data, indent=2)}")
    
    response = requests.post(url, headers=headers, json=meeting_data)
    print(f"Push API response: {response.status_code}, {response.text}")
    
    if response.status_code in [200, 201]:
        meeting_id = response.json().get("id")
        if meeting_id:
            frappe.db.set_value(
                "Event",
                event.name,
                "custom_calendar_event_id",  # Usamos custom_calendar_event_id
                meeting_id,
                update_modified=False
            )
            print(f"Assigned custom_calendar_event_id {meeting_id} to event {event.name}")
            frappe.db.commit()
            return True, f"Successfully pushed event {event.name} to HubSpot with ID {meeting_id}"
        else:
            error_msg = f"Meeting created but no ID returned for event {event.name}"
            print(error_msg)
            frappe.log_error(error_msg, "HubSpot Push Error")
            return False, error_msg
    else:
        error_msg = f"Error pushing event {event.name} to HubSpot: {response.status_code} - {response.text}"
        print(error_msg)
        frappe.log_error(error_msg, "HubSpot Push Error")
        return False, error_msg

@frappe.whitelist()
def update_hubspot_meeting(event, access_token, headers, owner_id=None):
    """Update an existing meeting in HubSpot."""
    custom_id = event.get("custom_calendar_event_id")  # Usamos custom_calendar_event_id
    if not custom_id:
        print(f"No custom_calendar_event_id found for event {event.name}. Cannot update.")
        return False, f"No custom_calendar_event_id found for event {event.name}."
    
    print(f"Updating existing meeting for event {event.name} with ID {custom_id}")
    
    participants = frappe.get_all(
        "Event Participants",
        filters={"parent": event.name},
        fields=["reference_doctype", "reference_docname"]
    )
    
    print(f"Event {event.name} - Number of participants found: {len(participants)}")
    
    start_time = get_datetime(event.starts_on)
    end_time = get_datetime(event.ends_on) if event.ends_on else (start_time + timedelta(minutes=30))
    start_timestamp = int(start_time.timestamp() * 1000)
    end_timestamp = int(end_time.timestamp() * 1000)
    
    contact_ids = []
    if participants:
        for participant in participants:
            print(f"Processing participant for event {event.name}: {participant}")
            if participant.reference_doctype == "Contact":
                try:
                    contact = frappe.get_doc("Contact", participant.reference_docname)
                    email = contact.email_id
                    first_name = contact.first_name
                    last_name = contact.last_name
                    print(f"Event {event.name} - Participant Contact:")
                    print(f"  Email: {email if email else 'Not set'}")
                    print(f"  First Name: {first_name if first_name else 'Not set'}")
                    print(f"  Last Name: {last_name if last_name else 'Not set'}")
                    
                    if email:
                        contact_id = get_hubspot_contact_id_by_email(email, access_token, headers)
                        if contact_id:
                            contact_ids.append(contact_id)
                        else:
                            contact_id = create_hubspot_contact(email, first_name, last_name, owner_id, access_token, headers)
                            if contact_id:
                                contact_ids.append(contact_id)
                            else:
                                print(f"Warning: Failed to create HubSpot contact for email {email}")
                    else:
                        print(f"Warning: No email found for Contact {participant.reference_docname}")
                except frappe.DoesNotExistError:
                    print(f"Error: Contact {participant.reference_docname} not found for event {event.name}")
            else:
                print(f"Participant for event {event.name} is not a Contact: {participant.reference_doctype}")
    else:
        print(f"No participants found for event {event.name}.")
    
    if not contact_ids:
        print(f"Skipping event {event.name}: No valid HubSpot contact IDs found.")
        return False, f"Skipping event {event.name}: No valid HubSpot contact IDs found."
    
    meeting_data = {
        "properties": {
            "hs_meeting_title": event.subject or "Reunión",
            "hs_meeting_start_time": start_timestamp,
            "hs_meeting_end_time": end_timestamp,
            "hs_meeting_body": event.description or "",
            "hs_timestamp": start_timestamp
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": 200
                    }
                ]
            } for contact_id in contact_ids
        ]
    }
    if owner_id:  # Solo agregar hubspot_owner_id si está presente
        meeting_data["properties"]["hubspot_owner_id"] = owner_id
    
    url = f"https://api.hubapi.com/crm/v3/objects/meetings/{custom_id}"
    print(f"Updating meeting in HubSpot: {event.name}")
    print(f"Meeting data: {json.dumps(meeting_data, indent=2)}")
    
    response = requests.patch(url, headers=headers, json=meeting_data)
    print(f"Update API response: {response.status_code}, {response.text}")
    
    if response.status_code in [200, 204]:
        print(f"Successfully updated event {event.name} in HubSpot with ID {custom_id}")
        return True, f"Successfully updated event {event.name} in HubSpot with ID {custom_id}"
    else:
        error_msg = f"Error updating event {event.name} in HubSpot: {response.status_code} - {response.text}"
        print(error_msg)
        frappe.log_error(error_msg, "HubSpot Update Error")
        return False, error_msg

@frappe.whitelist()
def push_hubspot_data(hubspot_doc):
    """Push events to HubSpot, creating or updating meetings based on custom_calendar_event_id, for events matching the specified calendar and with sync enabled."""
    print(f"Executing push_hubspot_data for doc: {hubspot_doc}")
    doc = frappe.get_doc("Calendar Hubspot", hubspot_doc)
    
    if not doc.push:
        print("Push is disabled.")
        return "Push is disabled."
    
    access_token = doc.get_access_token()
    calendar_id = doc.calendar_id  # Obtener el calendar_id del documento
    if not calendar_id:
        error_msg = "Calendar ID is not set in the Calendar Hubspot document."
        print(error_msg)
        frappe.throw(error_msg)
    
    print(f"Using access token: {access_token}, Calendar ID: {calendar_id}")
    
    # Filtrar eventos según los criterios especificados
    events = frappe.get_all(
        "Event",
        filters={
            "custom_calendar_provider": "Calendar Hubspot",
            "custom_calendar_id": calendar_id,
            "custom_sync_with_calendar_provider": 1  # Solo eventos con sync habilitado
        },
        fields=["name", "subject", "description", "starts_on", "ends_on", "custom_calendar_event_id", "custom_calendar_id"]
    )
    
    if not events:
        print(f"No events found matching provider 'Calendar Hubspot', calendar_id '{calendar_id}', and custom_sync_with_calendar_provider enabled.")
        return f"No events found matching provider 'Calendar Hubspot', calendar_id '{calendar_id}', and custom_sync_with_calendar_provider enabled."
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    owner_id = getattr(doc, "owner_id", None)  # Obtener owner_id si existe, None si no
    success_count = 0
    for event in events:
        try:
            # Verificar que custom_calendar_id coincide explícitamente
            if event.get("custom_calendar_id") != calendar_id:
                print(f"Skipping event {event.name}: custom_calendar_id '{event.custom_calendar_id}' does not match calendar_id '{calendar_id}'.")
                continue
                
            custom_id = event.get("custom_calendar_event_id")
            if custom_id:
                # Verificar si la reunión existe en HubSpot
                check_url = f"https://api.hubapi.com/crm/v3/objects/meetings/{custom_id}"
                print(f"Checking if meeting exists with custom_calendar_event_id: {custom_id}")
                check_response = requests.get(check_url, headers=headers)
                print(f"Check API response: {check_response.status_code}, {check_response.text}")
                
                if check_response.status_code == 200:
                    # La reunión existe, proceder a actualizar
                    success, message = update_hubspot_meeting(event, access_token, headers, owner_id)
                    if success:
                        success_count += 1
                        print(f"Successfully updated event {event.name}")
                    else:
                        print(f"Failed to update event {event.name}: {message}")
                else:
                    # La reunión no existe, crear una nueva
                    success, message = push_hubspot_meeting(event, access_token, headers, owner_id)
                    if success:
                        success_count += 1
                        print(f"Successfully created new meeting for event {event.name}")
                    else:
                        print(f"Failed to create meeting for event {event.name}: {message}")
            else:
                # No hay custom_calendar_event_id, crear una nueva reunión
                success, message = push_hubspot_meeting(event, access_token, headers, owner_id)
                if success:
                    success_count += 1
                    print(f"Successfully created new meeting for event {event.name}")
                else:
                    print(f"Failed to create meeting for event {event.name}: {message}")
                
        except Exception as e:
            error_msg = f"Error processing event {event.name}: {str(e)}"
            print(error_msg)
            frappe.log_error(error_msg, "HubSpot Push Exception")
            continue
    
    return f"Successfully processed {success_count}/{len(events)} events to HubSpot."