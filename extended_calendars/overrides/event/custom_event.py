# Copyright (c) 2025, Yeifer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.desk.doctype.event.event import Event

class CustomEvent(Event):
    def before_save(self):
        super(CustomEvent, self).before_save()
        self.set_custom_calendar_id()

    def set_custom_calendar_id(self):
        if not self.custom_calendar_provider or not self.custom_calendar:
            self.custom_calendar_id = None
            return

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