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
        print(f"Validating: usser={self.usser}, access_token={self.access_token}, owner_id={self.owner_id}")
        if not self.usser:
            frappe.throw("Please enter an email in the 'Usser' field.")
        if not self.access_token:
            frappe.throw("Please enter the access token in 'Access Token' field.")
        if not self.owner_id:
            frappe.throw("Please enter the owner ID in 'Owner Id' field.")
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
            "lastname": last_name if last_name else "X",
            "hubspot_owner_id": owner_id
        }
    }
    
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
def pull_hubspot_data(hubspot_doc):
    """Fetch ALL meeting data with participants from HubSpot API"""
    print(f"Executing pull_hubspot_data for doc: {hubspot_doc}")
    doc = frappe.get_doc("Calendar Hubspot", hubspot_doc)
    
    if not doc.pull:
        return {"success": False, "message": "Pull is disabled."}
    
    access_token = doc.get_access_token()
    print(f"Using access token: {access_token}")
    
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
                    continue

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
                                participants.append({
                                    "contact_id": contact_id,
                                    "properties": contact_data.get("properties", {})
                                })
                            else:
                                participants.append({"contact_id": contact_id})
                
                meeting["participants"] = participants
                all_meetings.append(meeting)
                
                time.sleep(0.1)

            if "paging" in data and "next" in data["paging"]:
                next_page = data["paging"]["next"]["after"]
            else:
                break

        result = {
            "total_meetings": total_meetings,
            "page_count": page_count,
            "meetings": all_meetings
        }
        
        print("\nHubSpot Meetings Data with Participants (Complete):")
        print(f"Total meetings fetched: {total_meetings} from {page_count} pages")
        print(json.dumps(result, indent=2))
        
        return {
            "success": True,
            "message": f"Successfully fetched {total_meetings} meetings with participants from {page_count} pages",
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
def push_hubspot_meeting(event, access_token, headers, owner_id):
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
            "hubspot_owner_id": owner_id,
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
                "custom_hubspot_calendar_id",
                meeting_id,
                update_modified=False
            )
            print(f"Assigned custom_hubspot_calendar_id {meeting_id} to event {event.name}")
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
def update_hubspot_meeting(event, access_token, headers, owner_id):
    """Update an existing meeting in HubSpot."""
    custom_id = event.get("custom_hubspot_calendar_id")
    if not custom_id:
        print(f"No custom_hubspot_calendar_id found for event {event.name}. Cannot update.")
        return False, f"No custom_hubspot_calendar_id found for event {event.name}."
    
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
            "hubspot_owner_id": owner_id,
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
    """Push all events to HubSpot, determining whether to create or update based on custom_hubspot_calendar_id."""
    print(f"Executing push_hubspot_data for doc: {hubspot_doc}")
    doc = frappe.get_doc("Calendar Hubspot", hubspot_doc)
    
    if not doc.push:
        print("Push is disabled.")
        return "Push is disabled."
    
    access_token = doc.get_access_token()
    print(f"Using access token: {access_token}")
    
    events = frappe.get_all(
        "Event",
        fields=["name", "subject", "description", "starts_on", "ends_on", "custom_hubspot_calendar_id"]
    )
    
    if not events:
        print("No events found to push to HubSpot.")
        return "No events found to push to HubSpot."
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    success_count = 0
    for event in events:
        try:
            custom_id = event.get("custom_hubspot_calendar_id")
            if custom_id:
                check_url = f"https://api.hubapi.com/crm/v3/objects/meetings/{custom_id}"
                print(f"Checking if meeting exists with custom_hubspot_calendar_id: {custom_id}")
                check_response = requests.get(check_url, headers=headers)
                print(f"Check API response: {check_response.status_code}, {check_response.text}")
                
                if check_response.status_code == 200:
                    success, message = update_hubspot_meeting(event, access_token, headers, doc.owner_id)
                    if success:
                        success_count += 1
                    else:
                        print(f"Failed to update event {event.name}: {message}")
                else:
                    success, message = push_hubspot_meeting(event, access_token, headers, doc.owner_id)
                    if success:
                        success_count += 1
                    else:
                        print(f"Failed to push event {event.name}: {message}")
            else:
                success, message = push_hubspot_meeting(event, access_token, headers, doc.owner_id)
                if success:
                    success_count += 1
                else:
                    print(f"Failed to push event {event.name}: {message}")
                
        except Exception as e:
            error_msg = f"Error processing event {event.name}: {str(e)}"
            print(error_msg)
            frappe.log_error(error_msg, "HubSpot Push Exception")
            continue
    
    return f"Successfully processed {success_count}/{len(events)} events to HubSpot."