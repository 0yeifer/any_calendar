import frappe
from frappe.integrations.doctype.google_calendar.google_calendar import (
    update_event_in_calendar as original_update_event_in_calendar,
    get_google_calendar_object as original_get_google_calendar_object,
)

def update_event_in_calendar(account, event, recurrence=None):
    event = frappe.get_doc("Event", {"google_calendar_event_id": event.get("id")})
    if (event and event.sync_with_google_calendar == 1):
        original_update_event_in_calendar(account, event, recurrence)
    else:
        return
    
def get_google_calendar_object(g_calendar):
    try:
        google_calendar, account = original_get_google_calendar_object(g_calendar)
    except Exception as e:
        account = frappe._dict()
        account.push_to_google_calendar = None
        google_calendar = None
        frappe.log_error(f"Error fetching Google Calendar object: {str(e)}")
    return google_calendar, account