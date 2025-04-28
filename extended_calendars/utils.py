import frappe
from extended_calendars.extended_calendars.doctype.calendar_hubspot.calendar_hubspot import (
    insert_event_in_calendar_hubspot,
    update_event_in_calendar_hubspot,
    delete_event_in_calendar_hubspot
)
from extended_calendars.extended_calendars.doctype.ghl_calendar.ghl_calendar import (
    insert_event_in_ghl_calendar,
    update_event_in_ghl_calendar,
    delete_event_in_ghl_calendar
)

def insert_event_in_calendar_provider(doc, method=None):
    if doc.custom_calendar_provider == "Calendar Hubspot":
        insert_event_in_calendar_hubspot(doc, method)
    elif doc.custom_calendar_provider == "GHL Calendar":
        insert_event_in_ghl_calendar(doc, method)

def update_event_in_calendar_provider(doc, method=None):
    if doc.custom_calendar_provider == "Calendar Hubspot":
        update_event_in_calendar_hubspot(doc, method)
    elif doc.custom_calendar_provider == "GHL Calendar":
        update_event_in_ghl_calendar(doc, method)

def delete_event_in_calendar_provider(doc, method=None):
    if doc.custom_calendar_provider == "Calendar Hubspot":
        delete_event_in_calendar_hubspot(doc, method)
    elif doc.custom_calendar_provider == "GHL Calendar":
        delete_event_in_ghl_calendar(doc, method)

