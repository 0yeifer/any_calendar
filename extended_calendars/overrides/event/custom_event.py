# Copyright (c) 2025, Yeifer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.desk.doctype.event.event import Event

class CustomEvent(Event):
    def before_save(self):
        try:
            original_provider = getattr(self, 'custom_calendar_provider', None)
            original_calendar = getattr(self, 'custom_calendar', None)

            # Nueva lógica para sync_with_google_calendar
            if (getattr(self, 'custom_sync_with_calendar_provider', 0) == 1 and 
                getattr(self, 'custom_calendar_provider', None) == "Google Calendar"):
                self.sync_with_google_calendar = 1

            if original_provider == "Google Calendar":
                self.google_calendar = getattr(self, 'custom_calendar', None) or None
                self.google_calendar_id = getattr(self, 'custom_calendar_id', None) or None
                self.google_calendar_event_id = getattr(self, 'custom_calendar_event_id', None) or None
                self.google_meet_link = getattr(self, 'custom_meet_link', None) or None
                self.pulled_from_google_calendar = getattr(self, 'custom_pulled_from_calendar_provider', 0) or 0

            self.set_custom_calendar_id()
            super(CustomEvent, self).before_save()

            frappe.log_error(f"Google fields set for {self.name}: cal={self.google_calendar}, pulled={self.pulled_from_google_calendar}")

        except Exception as e:
            frappe.log_error(f"Error in before_save {self.name}: {str(e)[:50]}")

    def after_insert(self):
        """
        Método que se ejecuta después de insertar un evento.
        Si el evento proviene de Google Calendar, llena los campos personalizados
        basados en los valores de Google Calendar, sin sobrescribir valores existentes
        a menos que sea necesario.
        """
        try:
            if not (getattr(self, 'pulled_from_google_calendar', 0) == 1 and getattr(self, 'google_calendar', None)):
                if not hasattr(self, 'custom_calendar_provider') or not self.custom_calendar_provider:
                    self.custom_calendar_provider = None
                if not hasattr(self, 'custom_calendar') or not self.custom_calendar:
                    self.custom_calendar = None
                if not hasattr(self, 'custom_calendar_id') or not self.custom_calendar_id:
                    self.custom_calendar_id = None
                if not hasattr(self, 'custom_calendar_event_id') or not self.custom_calendar_event_id:
                    self.custom_calendar_event_id = None
                if not hasattr(self, 'custom_meet_link') or not self.custom_meet_link:
                    self.custom_meet_link = None
                if not hasattr(self, 'custom_pulled_from_calendar_provider') or not self.custom_pulled_from_calendar_provider:
                    self.custom_pulled_from_calendar_provider = 0
            else:
                self.custom_calendar_provider = "Google Calendar"
                self.custom_calendar = getattr(self, 'google_calendar', None) or None
                self.custom_calendar_id = getattr(self, 'google_calendar_id', None) or None
                self.custom_calendar_event_id = getattr(self, 'google_calendar_event_id', None) or None
                self.custom_meet_link = getattr(self, 'google_meet_link', None) or None
                self.custom_pulled_from_calendar_provider = getattr(self, 'pulled_from_google_calendar', 0) or 0

            self.db_update()
            frappe.db.commit()
            
            frappe.log_error(f"Custom fields updated for {self.name} in after_insert")

        except Exception as e:
            frappe.log_error(f"Error in after_insert {self.name}: {str(e)}")


    def set_custom_calendar_id(self):
        """
        Método para establecer custom_calendar_id basado en custom_calendar_provider
        y custom_calendar.
        """
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
