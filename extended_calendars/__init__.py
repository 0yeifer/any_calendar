__version__ = "0.1.7"

# Overrides for Standard Frappe Doctypes 

from frappe.integrations.doctype.google_calendar import google_calendar
from extended_calendars.overrides.google_calendar.custom_google_calendar import (
    update_event_in_calendar as custom_update_event_in_calendar,
    get_google_calendar_object as custom_get_google_calendar_object,
)
google_calendar.update_event_in_calendar = custom_update_event_in_calendar
google_calendar.get_google_calendar_object = custom_get_google_calendar_object