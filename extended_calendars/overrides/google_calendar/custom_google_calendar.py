import frappe
from frappe.integrations.doctype.google_calendar.google_calendar import update_event_in_calendar as original_update_event_in_calendar

def update_event_in_calendar(account, event, recurrence=None):
    event = frappe.get_doc("Event", {"google_calendar_event_id": event.get("id")})
    if (event and event.sync_with_google_calendar == 1):
        original_update_event_in_calendar(account, event, recurrence)
    else:
        return