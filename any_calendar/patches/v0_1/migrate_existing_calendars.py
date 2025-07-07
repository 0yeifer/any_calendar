import frappe

def execute():
    google_events = frappe.get_all("Event", or_filters={"sync_with_google_calendar": 1, "pulled_from_google_calendar": 1})
    
    if not google_events:
        print("No events found to migrate.")
        return
    
    google_events_count = len(google_events)
    google_events_not_sync = 0
    print(f"Found {google_events_count} {'event' if google_events_count == 1 else 'events'} to migrate, updating now...")
    for event in google_events:
        doc = frappe.get_doc("Event", event.name)
        
        doc.custom_sync_with_calendar_provider = 1
        
        if doc.pulled_from_google_calendar == 1:
            doc.sync_with_google_calendar = 1
            doc.custom_pulled_from_calendar_provider = 1
        
        if not doc.google_calendar:
            doc.sync_with_google_calendar = 0
            doc.custom_sync_with_calendar_provider = 0
            google_events_not_sync += 1
            print(f"Sync event disabled for {doc.name} as google_calendar is not set.")
        
        if not frappe.db.exists("Google Calendar", doc.google_calendar):
            doc.sync_with_google_calendar = 0
            doc.custom_sync_with_calendar_provider = 0
            google_events_not_sync += 1
            print(f"Sync event disabled for {doc.name} as google_calendar {doc.google_calendar} does not exist.")
        
        doc.custom_calendar_provider = "Google Calendar"
        doc.custom_calendar = doc.google_calendar
        doc.custom_calendar_id = doc.google_calendar_id
        doc.custom_calendar_event_id = doc.google_calendar_event_id
        doc.custom_meet_link = doc.google_meet_link
        
        doc.db_update()
    
    total_events_migrated = google_events_count - google_events_not_sync
    print(f"Successfully migrated {total_events_migrated} {'event' if total_events_migrated == 1 else 'events'} to the new calendar system.")
    if google_events_not_sync:
        print(f"Check for {google_events_not_sync} sync events disabled due to missing data or invalid references.")
