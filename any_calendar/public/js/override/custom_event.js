// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on('Event', {
    custom_sync_with_calendar_provider: function(frm) {
        if (frm.doc.custom_sync_with_calendar_provider == 1 && frm.doc.custom_calendar_provider == "Google Calendar") {
            frm.set_value('sync_with_google_calendar', 1);
        } else {
            frm.set_value('sync_with_google_calendar', 0);
        }
    },
    custom_calendar_provider: function(frm) {
        frm.set_value('custom_calendar', "");
        if (frm.doc.custom_calendar_provider == "Google Calendar") {
            frm.set_value('sync_with_google_calendar', frm.doc.custom_sync_with_calendar_provider);
        } else {
            frm.set_value('sync_with_google_calendar', 0);
        }
    },
    custom_calendar: function(frm) {
        if (frm.doc.custom_calendar_provider == "Google Calendar") {
            console.log("Google Calendar log", frm.doc.custom_calendar);
            frm.set_value('google_calendar', frm.doc.custom_calendar);

        } else {
            frm.set_value('google_calendar', "");
        }
    }
  });
  

  
  
  