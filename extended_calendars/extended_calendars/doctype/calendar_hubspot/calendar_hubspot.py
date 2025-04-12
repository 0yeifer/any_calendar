# Copyright (c) 2025, Yeifer and contributors
# For license information, please see license.txt

import frappe
import json
import time
from frappe.model.document import Document
import requests
from datetime import datetime, timedelta
from frappe.utils import get_datetime

# Constantes para URLs de la API de HubSpot
HUBSPOT_API_BASE = "https://api.hubapi.com/crm/v3"
CONTACTS_SEARCH_URL = f"{HUBSPOT_API_BASE}/objects/contACTS/search"
CONTACTS_URL = f"{HUBSPOT_API_BASE}/objects/contACTS"
MEETINGS_URL = f"{HUBSPOT_API_BASE}/objects/meetings"
MEETING_ASSOCIATIONS_URL = f"{MEETINGS_URL}/{{meeting_id}}/associations/contact"
CONTACT_URL = f"{HUBSPOT_API_BASE}/objects/contACTS/{{contact_id}}"

# Propiedades de reuniones de HubSpot
MEETING_PROPERTIES = [
    "hs_meeting_title",
    "hs_meeting_start_time",
    "hs_meeting_end_time",
    "hs_meeting_body"
]

# Códigos de estado HTTP exitosos
SUCCESS_STATUS_CODES = {200, 201, 204}

# Constante para la categoría y tipo de asociación
HUBSPOT_ASSOCIATION = {
    "associationCategory": "HUBSPOT_DEFINED",
    "associationTypeId": 200
}


@frappe.whitelist()
def sync_hubspot_data(hubspot_doc):
    """Execute pull followed by push for HubSpot calendar synchronization."""
    print(f"Executing sync_hubspot_data for doc: {hubspot_doc}")
    
    # Inicializar resultados
    pull_result = {"success": False, "message": "Pull skipped (disabled)", "stats": {}}
    push_result = {"success": False, "message": "Push skipped (disabled)", "stats": {"total_events": 0, "successful": 0, "skipped": 0}}

    doc = frappe.get_doc("Calendar Hubspot", hubspot_doc)

    # Ejecutar pull si está habilitado
    if doc.pull:
        print("Running pull_hubspot_data...")
        pull_result = pull_hubspot_data(hubspot_doc)

    # Ejecutar push si está habilitado
    if doc.push:
        print("Running push_hubspot_data...")
        push_result = push_hubspot_data(hubspot_doc)
    
    # Combinar resultados
    combined_message = (
        f"<b>Pull Result:</b> {pull_result.get('message', 'No pull result')}<br>"
        f"<b>Push Result:</b> {push_result.get('message', 'No push result')}"
    )
    
    if pull_result.get("stats", {}).get("total_meetings"):
        combined_message += (
            f"<br><br><b>Pull Stats:</b><br>"
            f"- Total Meetings: {pull_result['stats']['total_meetings']}<br>"
            f"- Events Created: {pull_result['stats']['created_count']}<br>"
            f"- Events Updated: {pull_result['stats']['updated_count']}<br>"
            f"- Events Skipped: {pull_result['stats']['skipped_count']}"
        )
    # Incluir estadísticas si están disponibles
    if push_result.get("stats", {}).get("total_events"):
        combined_message += (
            f"<br><br><b>Push Stats:</b><br>"
            f"- Total Events: {push_result['stats']['total_events']}<br>"
            f"- Successfully Pushed: {push_result['stats']['successful']}<br>"
            f"- Skipped: {push_result['stats']['skipped']}"
        )
    
    success = pull_result.get("success", False) or push_result.get("success", False)
    
    return {
        "success": success,
        "message": combined_message,
        "pull_result": pull_result,
        "push_result": push_result,
    }



def get_headers(access_token):
    """Genera encabezados HTTP para solicitudes a HubSpot."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

def create_association(contact_id):
    """Crea una estructura de asociación para un contacto."""
    return {
        "to": {"id": contact_id},
        "types": [HUBSPOT_ASSOCIATION]
    }

def get_contact_ids_from_participants(participants, access_token, headers, owner_id=None):
    """Obtiene o crea IDs de contactos en HubSpot a partir de participantes de Frappe."""
    contact_ids = []
    for participant in participants:
        print(f"Processing participant: {participant}")
        if participant.reference_doctype != "Contact":
            print(f"Participant is not a Contact: {participant.reference_doctype}")
            continue
        try:
            contact = frappe.get_doc("Contact", participant.reference_docname)
            email = contact.email_id
            first_name = contact.first_name
            last_name = contact.last_name
            print(f"Participant Contact - Email: {email or 'Not set'}, "
                  f"First Name: {first_name or 'Not set'}, Last Name: {last_name or 'Not set'}")
            
            if not email:
                print(f"Warning: No email found for Contact {participant.reference_docname}")
                continue
                
            contact_id = get_hubspot_contact_id_by_email(email, access_token, headers)
            if not contact_id:
                contact_id = create_hubspot_contact(email, first_name, last_name, owner_id, access_token, headers)
            if contact_id:
                contact_ids.append(contact_id)
            else:
                print(f"Warning: Failed to create HubSpot contact for email {email}")
        except frappe.DoesNotExistError:
            print(f"Error: Contact {participant.reference_docname} not found")
    return contact_ids

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
        response = requests.post(CONTACTS_SEARCH_URL, headers=headers, json=payload)
        print(f"API response for email {email}: {response.status_code}, {response.text}")
        
        if response.status_code in SUCCESS_STATUS_CODES:
            data = response.json()
            results = data.get("results", [])
            if results:
                contact_id = results[0].get("id")
                print(f"Found contact ID {contact_id} for email {email}")
                return contact_id
            print(f"No contact found for email {email}")
            return None
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
    
    payload = {
        "properties": {
            "email": email,
            "firstname": first_name if first_name else "X",
            "lastname": last_name if last_name else "X"
        }
    }
    if owner_id:
        payload["properties"]["hubspot_owner_id"] = owner_id
    
    try:
        response = requests.post(CONTACTS_URL, headers=headers, json=payload)
        print(f"Create contact API response: {response.status_code}, {response.text}")
        
        if response.status_code in SUCCESS_STATUS_CODES:
            data = response.json()
            contact_id = data.get("id")
            print(f"Successfully created contact with ID {contact_id} for email {email}")
            return contact_id
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
    calendar_id = doc.calendar_id
    headers = get_headers(access_token)
    print(f"Using access token: {access_token}, Calendar ID: {calendar_id}")
    
    params = {
        "properties": ",".join(MEETING_PROPERTIES),  # Corregido: usar join en lugar de currents
        "limit": "100"
    }

    all_meetings = []
    next_page = None
    page_count = 0
    total_meetings = 0
    created_count = 0
    updated_count = 0
    skipped_count = 0

    try:
        while True:
            page_count += 1
            current_params = params.copy()
            if next_page:
                current_params["after"] = next_page

            print(f"Fetching page {page_count} of meetings...")
            response = requests.get(MEETINGS_URL, headers=headers, params=current_params)
            
            if response.status_code not in SUCCESS_STATUS_CODES:
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
                    skipped_count += 1
                    continue

                # Buscar el evento existente incluyendo el campo custom_sync_with_calendar_provider
                event_info = frappe.db.get_value(
                    "Event",
                    {"custom_calendar_event_id": meeting_id},
                    ["name", "custom_sync_with_calendar_provider"],
                    as_dict=True
                )
                
                event_exists = bool(event_info)
                sync_enabled = event_exists and event_info.get("custom_sync_with_calendar_provider") == 1
                
                print(f"Checking event with meeting_id {meeting_id}: "
                      f"Exists={event_exists}, SyncEnabled={sync_enabled}")

                # Si el evento existe pero no tiene sync habilitado, saltar
                if event_exists and not sync_enabled:
                    print(f"Skipping meeting {meeting_id}: Sync not enabled for existing event")
                    skipped_count += 1
                    continue
                
                properties = meeting.get("properties", {})
                subject = properties.get("hs_meeting_title", "Reunión")
                start_time_str = properties.get("hs_meeting_start_time", "1970-01-01T00:00:00Z")
                end_time_str = properties.get("hs_meeting_end_time", "1970-01-01T00:00:00Z")
                
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                start_time_formatted = start_time.strftime("%Y-%m-%d %H:%M:%S")
                end_time_formatted = end_time.strftime("%Y-%m-%d %H:%M:%S")
                description = properties.get("hs_meeting_body", "")

                # Obtener participantes
                participants = []
                assoc_response = requests.get(
                    MEETING_ASSOCIATIONS_URL.format(meeting_id=meeting_id),
                    headers=headers
                )
                if assoc_response.status_code in SUCCESS_STATUS_CODES:
                    assoc_data = assoc_response.json()
                    for result in assoc_data.get("results", []):
                        contact_id = result.get("id")
                        if contact_id:
                            contact_response = requests.get(
                                CONTACT_URL.format(contact_id=contact_id),
                                headers=headers,
                                params={"properties": "firstname,lastname,email"}
                            )
                            if contact_response.status_code in SUCCESS_STATUS_CODES:
                                contact_data = contact_response.json()
                                contact_props = contact_data.get("properties", {})
                                participants.append({
                                    "email": contact_props.get("email"),
                                    "first_name": contact_props.get("firstname"),
                                    "last_name": contact_props.get("lastname")
                                })

                # Preparar datos del evento
                event_data = {
                    "subject": subject,
                    "starts_on": start_time_formatted,
                    "ends_on": end_time_formatted,
                    "description": description,
                    "custom_calendar_event_id": meeting_id,
                    "custom_calendar_provider": "Calendar Hubspot",
                    "custom_hubspot_calendar_id": calendar_id,
                    "custom_pulled_from_calendar_provider": 1,
                    "custom_calendar": hubspot_doc,
                    "custom_sync_with_calendar_provider": 1
                }

                # Procesar participantes
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

                if event_exists:
                    event_name = event_info["name"]
                    print(f"Updating existing event {event_name}...")
                    event = frappe.get_doc("Event", event_name)
                    event.update(event_data)
                    event.set("event_participants", event_participants)
                    event.save(ignore_permissions=True)
                    updated_count += 1
                    print(f"Updated event {event_name} with meeting_id {meeting_id}")
                else:
                    print(f"Creating new event for meeting_id {meeting_id}...")
                    event = frappe.get_doc({
                        "doctype": "Event",
                        **event_data,
                        "event_participants": event_participants
                    })
                    event.insert(ignore_permissions=True)
                    created_count += 1
                    print(f"Created new event {event.name} with meeting_id {meeting_id}")

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
            "skipped_count": skipped_count,
            "meetings": all_meetings
        }
        
        print("\nHubSpot Meetings Data Processed:")
        print(f"Total meetings fetched: {total_meetings} from {page_count} pages")
        print(f"Events created: {created_count}, Events updated: {updated_count}, Events skipped: {skipped_count}")
        return {
            "success": True,
            "message": f"Processed {total_meetings} meetings: {created_count} created, {updated_count} updated, {skipped_count} skipped",
            "stats": result
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
def push_hubspot_data(hubspot_doc):
    """Push events to HubSpot, creating or updating meetings based on custom_calendar_event_id."""
    print(f"Executing push_hubspot_data for doc: {hubspot_doc}")
    doc = frappe.get_doc("Calendar Hubspot", hubspot_doc)
    
    if not doc.push:
        print("Push is disabled.")
        return {
            "success": False,
            "message": "Push is disabled.",
            "stats": {"total_events": 0, "successful": 0, "skipped": 0}
        }
    
    access_token = doc.get_access_token()
    calendar_id = doc.calendar_id
    if not calendar_id:
        error_msg = "Calendar ID is not set in the Calendar Hubspot document."
        print(error_msg)
        frappe.throw(error_msg)
    
    headers = get_headers(access_token)
    print(f"Using access token: {access_token}, Calendar ID: {calendar_id}")
    
    # Filtrar eventos que cumplan con los criterios exactos
    events = frappe.get_all(
        "Event",
        filters={
            "custom_calendar_provider": "Calendar Hubspot",
            "custom_sync_with_calendar_provider": 1,
            "custom_calendar": hubspot_doc
        },
        fields=["name", "subject", "description", "starts_on", "ends_on", 
                "custom_calendar_event_id"]
    )
    
    if not events:
        print(f"No events found for calendar {hubspot_doc} with sync enabled.")
        return {
            "success": True,
            "message": f"No events found for calendar {hubspot_doc} with sync enabled.",
            "stats": {"total_events": 0, "successful": 0, "skipped": 0}
        }
    
    owner_id = getattr(doc, "owner_id", None)
    success_count = 0
    skipped_count = 0
    
    for event in events:
        try:
            print(f"Processing event {event.name}: sync_enabled={event.custom_sync_with_calendar_provider}")
            
            # Procesar el evento
            custom_id = event.get("custom_calendar_event_id")
            if custom_id:
                print(f"Found existing meeting ID: {custom_id}")
                response = requests.get(f"{MEETINGS_URL}/{custom_id}", headers=headers)
                print(f"Check API response: {response.status_code}")
                
                if response.status_code in SUCCESS_STATUS_CODES:
                    success, message = update_hubspot_meeting(event, access_token, headers, owner_id)
                else:
                    success, message, meeting_id = push_hubspot_meeting(event, access_token, headers, owner_id)
            else:
                success, message, meeting_id = push_hubspot_meeting(event, access_token, headers, owner_id)
                
            if success:
                success_count += 1
                print(f"Successfully processed event {event.name}: {message}")
            else:
                print(f"Failed to process event {event.name}: {message}")
                skipped_count += 1
                
        except Exception as e:
            error_msg = f"Error processing event {event.name}: {str(e)}"
            print(error_msg)
            frappe.log_error(error_msg, "HubSpot Push Exception")
            skipped_count += 1
            continue
    
    result = {
        "success": True,
        "message": f"Processed {success_count}/{len(events)} events to HubSpot. Skipped {skipped_count} events.",
        "stats": {
            "total_events": len(events),
            "successful": success_count,
            "skipped": skipped_count
        }
    }
    print(json.dumps(result, indent=2))
    return result


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
    
    contact_ids = get_contact_ids_from_participants(participants, access_token, headers, owner_id)
    
    if not contact_ids:
        print(f"Skipping event {event.name}: No valid HubSpot contact IDs found.")
        return False, f"No valid HubSpot contact IDs found."
    
    meeting_data = {
        "properties": {
            "hs_meeting_title": event.subject or "Reunión",
            "hs_meeting_start_time": start_timestamp,
            "hs_meeting_end_time": end_timestamp,
            "hs_meeting_body": event.description or "",
            "hs_timestamp": start_timestamp
        },
        "associations": [create_association(contact_id) for contact_id in contact_ids]
    }
    if owner_id:
        meeting_data["properties"]["hubspot_owner_id"] = owner_id
    
    print(f"Pushing new meeting to HubSpot: {event.name}")
    print(f"Meeting data: {json.dumps(meeting_data, indent=2)}")
    
    response = requests.post(MEETINGS_URL, headers=headers, json=meeting_data)
    print(f"Push API response: {response.status_code}, {response.text}")
    
    if response.status_code in SUCCESS_STATUS_CODES:
        meeting_id = response.json().get("id")
        if meeting_id:
            frappe.db.set_value(
                "Event",
                event.name,
                "custom_calendar_event_id",
                meeting_id,
                update_modified=False
            )
            frappe.db.commit()
            return True, f"Successfully pushed event {event.name} to HubSpot with ID {meeting_id}", meeting_id
        error_msg = f"Meeting created but no ID returned for event {event.name}"
        print(error_msg)
        frappe.log_error(error_msg, "HubSpot Push Error")
        return False, error_msg, None
    error_msg = f"Error pushing event {event.name} to HubSpot: {response.status_code} - {response.text}"
    print(error_msg)
    frappe.log_error(error_msg, "HubSpot Push Error")
    return False, error_msg, None

@frappe.whitelist()
def update_hubspot_meeting(event, access_token, headers, owner_id=None):
    """Update an existing meeting in HubSpot."""
    custom_id = event.get("custom_calendar_event_id")
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
    
    contact_ids = get_contact_ids_from_participants(participants, access_token, headers, owner_id)
    
    if not contact_ids:
        print(f"Skipping event {event.name}: No valid HubSpot contact IDs found.")
        return False, f"No valid HubSpot contact IDs found."
    
    meeting_data = {
        "properties": {
            "hs_meeting_title": event.subject or "Reunión",
            "hs_meeting_start_time": start_timestamp,
            "hs_meeting_end_time": end_timestamp,
            "hs_meeting_body": event.description or "",
            "hs_timestamp": start_timestamp
        },
        "associations": [create_association(contact_id) for contact_id in contact_ids]
    }
    if owner_id:
        meeting_data["properties"]["hubspot_owner_id"] = owner_id
    
    url = f"{MEETINGS_URL}/{custom_id}"
    print(f"Updating meeting in HubSpot: {event.name}")
    print(f"Meeting data: {json.dumps(meeting_data, indent=2)}")
    
    response = requests.patch(url, headers=headers, json=meeting_data)
    print(f"Update API response: {response.status_code}, {response.text}")
    
    if response.status_code in SUCCESS_STATUS_CODES:
        print(f"Successfully updated event {event.name} in HubSpot with ID {custom_id}")
        return True, f"Successfully updated event {event.name} in HubSpot with ID {custom_id}"
    error_msg = f"Error updating event {event.name} in HubSpot: {response.status_code} - {response.text}"
    print(error_msg)
    frappe.log_error(error_msg, "HubSpot Update Error")
    return False, error_msg

@frappe.whitelist()
def delete_hubspot_meeting(event, access_token, headers):
    """Delete a meeting in HubSpot."""
    custom_id = event.get("custom_calendar_event_id")
    if not custom_id:
        print(f"No custom_calendar_event_id found for event {event.name}. Cannot delete.")
        return False, f"No custom_calendar_event_id found for event {event.name}."
    
    url = f"{MEETINGS_URL}/{custom_id}"
    print(f"Deleting meeting in HubSpot: {event.name}")
    
    response = requests.delete(url, headers=headers)
    print(f"Delete API response: {response.status_code}, {response.text}")
    
    if response.status_code in SUCCESS_STATUS_CODES:
        print(f"Successfully deleted event {event.name} in HubSpot with ID {custom_id}")
        return True, f"Successfully deleted event {event.name} in HubSpot with ID {custom_id}"
    error_msg = f"Error deleting event {event.name} in HubSpot: {response.status_code} - {response.text}"
    print(error_msg)
    frappe.log_error(error_msg, "HubSpot Delete Error")
    return False, error_msg

def insert_event_in_calendar_hubspot(doc, method = None):
    """Insert event in HubSpot calendar."""
    try:
        if (doc.custom_sync_with_calendar_provider == 1 
            and doc.custom_calendar_provider == "Calendar Hubspot" 
            and doc.custom_calendar
            and not doc.custom_calendar_event_id):
            calendar = frappe.get_doc("Calendar Hubspot", doc.custom_calendar)
            event = frappe.get_doc("Event", doc.name)
            access_token = calendar.get_access_token()
            headers = get_headers(access_token)
            owner_id = calendar.owner_id

            success, message, meeting_id = push_hubspot_meeting(event, access_token, headers, owner_id)
            if success:
                event.custom_calendar_event_id = meeting_id
                event.db_update()
                frappe.msgprint(message)
        
    except frappe.DoesNotExistError:
        print(f"Error: Document {doc.name} does not exist.")
        frappe.log_error(f"Document {doc.name} does not exist.", "HubSpot Insert Event Error")



    except Exception as e:
        frappe.log_error(f"Error inserting event in HubSpot calendar: {str(e)}", "HubSpot Insert Event Error")
        print(f"Error inserting event in HubSpot calendar: {str(e)}")



def update_event_in_calendar_hubspot(doc, method = None):
    """Update event in HubSpot calendar."""
    try:
        if (doc.custom_sync_with_calendar_provider == 1 
            and doc.custom_calendar_provider == "Calendar Hubspot" 
            and doc.custom_calendar
            and doc.custom_calendar_event_id):
            calendar = frappe.get_doc("Calendar Hubspot", doc.custom_calendar)
            event = frappe.get_doc("Event", doc.name)
            access_token = calendar.get_access_token()
            headers = get_headers(access_token)
            owner_id = calendar.owner_id

            success, message = update_hubspot_meeting(event, access_token, headers, owner_id)
            if success:
                frappe.msgprint(message)
            else:
                frappe.msgprint(f"Failed to update HubSpot meeting: {message}")
    except frappe.DoesNotExistError:
        print(f"Error: Document {doc.name} does not exist.")
        frappe.log_error(f"Document {doc.name} does not exist.", "HubSpot Update Event Error")
    except Exception as e:
        frappe.log_error(f"Error updating event in HubSpot calendar: {str(e)}", "HubSpot Update Event Error")
        print(f"Error updating event in HubSpot calendar: {str(e)}")
        frappe.msgprint(f"Error updating event in HubSpot calendar: {str(e)}")

def delete_event_in_calendar_hubspot(doc, method = None):
    """Delete event in HubSpot calendar."""
    try:
        if (doc.custom_sync_with_calendar_provider == 1 
            and doc.custom_calendar_provider == "Calendar Hubspot" 
            and doc.custom_calendar
            and doc.custom_calendar_event_id):
            calendar = frappe.get_doc("Calendar Hubspot", doc.custom_calendar)
            event = frappe.get_doc("Event", doc.name)
            access_token = calendar.get_access_token()
            headers = get_headers(access_token)

            success, message = delete_hubspot_meeting(event, access_token, headers)
            if success:
                frappe.msgprint(message)
            else:
                frappe.msgprint(f"Failed to delete HubSpot meeting: {message}")
    except frappe.DoesNotExistError:
        print(f"Error: Document {doc.name} does not exist.")
        frappe.log_error(f"Document {doc.name} does not exist.", "HubSpot Delete Event Error")
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error while deleting event in HubSpot calendar: {str(e)}"
        print(error_msg)
        frappe.log_error(error_msg, "HubSpot Delete Event Request Error")
        frappe.msgprint(error_msg)
    except Exception as e:
        frappe.log_error(f"Error deleting event in HubSpot calendar: {str(e)}", "HubSpot Delete Event Error")
        print(f"Error deleting event in HubSpot calendar: {str(e)}")
        frappe.msgprint(f"Error deleting event in HubSpot calendar: {str(e)}")
