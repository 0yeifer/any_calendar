# Copyright (c) 2025, Yeifer and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.event.event import Event
from frappe.utils import (
	getdate,
	now_datetime,
)

class CustomEvent(Event):
    
    def validate(self):
        if not self.starts_on:
            self.starts_on = now_datetime()
    
        # if start == end this scenario doesn't make sense i.e. it starts and ends at the same second!
        self.ends_on = None if self.starts_on == self.ends_on else self.ends_on

        if self.starts_on and self.ends_on:
            self.validate_from_to_dates("starts_on", "ends_on")

        if self.repeat_on == "Daily" and self.ends_on and getdate(self.starts_on) != getdate(self.ends_on):
            frappe.throw(_("Daily Events should finish on the Same Day."))

        if self.sync_with_google_calendar and not self.google_calendar:
            self.sync_with_google_calendar = 0
            frappe.msgprint(_("Select Google Calendar to which event should be synced."), indicator="red")

        if not self.sync_with_google_calendar:
            self.add_video_conferencing = 0

    def before_save(self):
        try:
            
            if (self.sync_with_google_calendar == 1 and frappe.db.exists("Google Calendar", self.google_calendar)):
                self.custom_sync_with_calendar_provider = 1
                self.custom_calendar_provider = "Google Calendar"
                self.custom_calendar = self.google_calendar

            if (self.sync_with_google_calendar == 1 and self.custom_sync_with_calendar_provider == 1):
                if (self.custom_calendar_provider != "Google Calendar" or not frappe.db.exists("Google Calendar", self.custom_calendar)):
                    self.sync_with_google_calendar = 0
            else:
                self.sync_with_google_calendar = 0 

            if (self.custom_sync_with_calendar_provider == 1):
                self.sync_with_google_calendar = 0
                if (self.custom_calendar_provider == "Google Calendar" and self.custom_calendar):
                    if frappe.db.exists("Google Calendar", self.custom_calendar):
                        self.sync_with_google_calendar = self.custom_sync_with_calendar_provider
                        self.google_calendar = self.custom_calendar
                elif (self.custom_calendar_provider and self.custom_calendar):
                    self.set_custom_calendar_id()

            super(CustomEvent, self).before_save()
        except Exception as e:
            frappe.log_error(f"Error in before_save {self.name}: {str(e)[:50]}")

    def after_insert(self):
        try:
            calendar_exist = frappe.db.exists("Google Calendar", self.google_calendar)

            if (self.google_calendar and calendar_exist):
                self.sync_with_google_calendar = 1
                self.custom_sync_with_calendar_provider = self.sync_with_google_calendar
                self.custom_calendar_provider = "Google Calendar"
                self.custom_calendar = self.google_calendar
                self.custom_calendar_id = self.google_calendar_id
                self.custom_calendar_event_id = self.google_calendar_event_id
                self.custom_meet_link = self.google_meet_link
                self.custom_pulled_from_calendar_provider = self.pulled_from_google_calendar

                self.db_update()
            
        except Exception as e:
            frappe.log_error(f"Error in after_insert {self.name}: {str(e)}")

    def set_custom_calendar_id(self):
        try:
            calendar_id = frappe.get_value(
                self.custom_calendar_provider,
                self.custom_calendar,
                "calendar_id" 
            )
            self.custom_calendar_id = calendar_id if calendar_id else None

        except Exception as e:
            frappe.log_error(f"Error fetching calendar_id: {str(e)}")
            self.custom_calendar_id = None
