# Copyright (c) 2025, Yeifer and contributors
# For license information, please see license.txt

import frappe
import requests

from frappe.model.document import Document

class GoujanaCalendar(Document):
    
    def pull_events_from_provider(self):
        """Método para obtener datos del proveedor."""
        # Get auth data
        access_token = self.access_token
        cookie_value = self.cookie_value
  
        if not access_token or not cookie_value:
            frappe.throw("Access Token and Cookie Value are required to pull data from the provider.")
    
        headers = {
            "X-API-TOKEN": access_token,
            "Cookie": cookie_value
        }
  
        base_url = "https://goujana.co"
        endpoint = "/api/v1/schedule/appointment/"
  
        api_url = f"{base_url}{endpoint}"
  
        try:
            response = requests.request(
                "GET",
                api_url,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()  # Lanza un error si la respuesta no es exitosa (código 2xx)
            content = response.json()
            return content
        except Exception as e:
            raise frappe.ValidationError(f"Error al realizar la solicitud: {str(e)}")
   
    def map_data_to_push(self, data):
        """Map data to the structure required by the provider."""
        fields_to_map = {
            "subject": "text",
            "description": "observations",
            "starts_on": "start_date",
            "ends_on": "end_date",
            "custom_goujana_customer_id": "customer",
            "custom_calendar_id": "calendar",
        }
        
        mapped_data = {}
        
        for key, value in fields_to_map.items():
            if key not in data:
                frappe.throw(f"Missing required field for push: {key}")
            
            mapped_data[value] = data[key]
        
        return mapped_data
    
    def map_data_from_pull(self, data):
        fields_to_map = {
            "text": "subject",
            "observations": "description",
            "start_date": "starts_on",
            "end_date": "ends_on",
            "customer.id": "custom_goujana_customer_id",
            "calendar.id": "custom_calendar_id",
            "id": "custom_calendar_event_id",
        }
        
        mapped_data = {}
        
        for key, value in fields_to_map.items():
            keys = key.split('.')
            data_value = data
            for k in keys:
                if isinstance(data_value, dict) and k in data_value:
                    data_value = data_value[k]
                else:
                    data_value = None
                    break
            mapped_data[value] = data_value
        
        calendar_label = data.get("calendar", {}).get("label", "")
        calendar_name = (calendar_label.split("|")[0]).strip() if calendar_label else ""
        calendar_doc_name = frappe.db.get_value("Goujana Calendar", {"calendar_name": calendar_name}, "name")
        
        mapped_data["custom_calendar"] = calendar_doc_name
        mapped_data["custom_calendar_provider"] = "Goujana Calendar"
        mapped_data["custom_sync_with_calendar_provider"] = True
        
        return mapped_data
	
    def create_bulk_events(self, data_bulk):
        """Create events in bulk from mapped data."""
        if not data_bulk:
            frappe.throw("No hay datos para crear eventos.")
        
        try:
            for event_data in data_bulk:
                event_doc = None
                custom_calendar_event_id = event_data.get("custom_calendar_event_id")
                
                existing_event = frappe.db.exists("Event", {"custom_calendar_event_id": custom_calendar_event_id})
                if existing_event:
                    event_doc = frappe.get_doc("Event", existing_event)
                
                if not event_doc:
                    event_doc = frappe.new_doc("Event")
                
                event_doc.update(event_data)
            
                event_doc.save()
            
            frappe.db.commit()
            
        except Exception as e:
            error_msg = f"Error al crear eventos en bloque: {str(e)}"
            frappe.log_error(
                title="Goujana Calendar Bulk Event Creation Error",
                message=error_msg,
                doctype="Goujana Calendar",
                docname=self.name
            )
    
    def push_bulk_events(self, data_bulk):
        """Push events in bulk to the provider."""
        if not data_bulk:
            frappe.throw("No hay datos para enviar eventos al proveedor.")
        
        access_token = self.access_token
        cookie_value = self.cookie_value
        
        if not access_token or not cookie_value:
            frappe.throw("Access Token and Cookie Value are required to push data to the provider.")
        
        headers = {
            "X-API-TOKEN": access_token,
            "Cookie": cookie_value,
            "Content-Type": "application/json"
        }
        
        base_url = "https://goujana.co"
        endpoint = "/api/v1/schedule/appointment/"
        
        api_url = f"{base_url}{endpoint}"
        
        for event_data in data_bulk:
            try:
                response = requests.post(
                    api_url,
                    headers=headers,
                    json=event_data,
                    timeout=10
                )
                response.raise_for_status()
            except Exception as e:
                error_msg = f"Error al enviar evento: {str(e)}"
                frappe.log_error(
                    title="Goujana Calendar Bulk Event Push Error",
                    message=error_msg,
                    doctype="Goujana Calendar",
                    docname=self.name
                )
            
    def retrive_bulk_events(self):
        """Recupera eventos en bloque desde el proveedor."""
        fmt = "%Y-%m-%dT%H:%i:%sZ"
        related_events = frappe.get_all("Event", filters=[
            ["custom_sync_with_calendar_provider", "=", True],
            ["custom_calendar_provider", "=", "Goujana Calendar"],
            ["custom_calendar_event_id", "in", ["", None]]
        ], fields=[
            "name",
            "subject",
            "description",
            f"DATE_FORMAT(starts_on, '{fmt}') as starts_on",
            f"DATE_FORMAT(ends_on, '{fmt}') as ends_on",
            "custom_goujana_customer_id",
            "custom_calendar_id"
        ])
        
        return related_events
    
    def process_pull(self):
        """Procesa la sincronización de eventos desde el proveedor."""
        pull_result = self.pull_events_from_provider()
        mapped_bulk_data = []
        
        if pull_result:
            mapped_bulk_data = [self.map_data_from_pull(event) for event in pull_result.get("results", [])]
        
        if mapped_bulk_data:
            self.create_bulk_events(mapped_bulk_data)
        
        return {"success": True, "message": "Eventos sincronizados correctamente desde Goujana Calendar."}
    
    def process_push(self):
        """Procesa la sincronización de eventos hacia el proveedor."""
        push_data = self.retrive_bulk_events()
        mapped_bulk_data = []
        
        if push_data:
            mapped_bulk_data = [self.map_data_to_push(event) for event in push_data]
           
        if mapped_bulk_data:
            self.push_bulk_events(mapped_bulk_data)
        
        return {"success": True, "message": "Eventos sincronizados correctamente hacia Goujana Calendar."}

@frappe.whitelist()
def sync(doc_name=None):
    """Sincronización con proveedor.""" 
    try:
        doc = frappe.get_doc("Goujana Calendar", doc_name)

        if doc.pull:
            pull_result = doc.process_pull()
        
        #if doc.push:
        #    push_result = doc.process_push()
        
        return {
            "success": True,
            "message": "Sincronización completada correctamente.", 
            "pull_result": pull_result if doc.pull else None,
            #"push_result": push_result if doc.push else None
        }
    
    except Exception as e:
        error_msg = f"Error en sync goujana calendar: {str(e)}"
        frappe.log_error("Goujana Calendar Sync Error", error_msg)
        return {"success": False, "message": error_msg}

@frappe.whitelist()
def sync_all_goujana_calendars():
    """Sincronización de todos los calendarios de Goujana Calendar."""
    try:
        calendars = frappe.get_all("Goujana Calendar", fields=["name"])
        results = []
        
        for calendar in calendars:
            result = sync(doc_name=calendar.name)
            results.append(result)
        
        frappe.log_error("Goujana Calendar Sync All", f"Calendars Synced: {len(results)}")
        
        return {"success": True, "results": results}
    
    except Exception as e:
        error_msg = f"Error en sync_all_calendars: {str(e)}"
        frappe.log_error("Goujana Calendar Sync All Error", error_msg)
        return {"success": False, "message": error_msg}
    
@frappe.whitelist()
def test_insert(doc_name=None):
    """Test insert event in Goujana Calendar."""
    try:
        doc = frappe.get_doc("Event", doc_name)
        event_data = insert_event_in_goujana_calendar(doc)
        return {"success": True, "event_data": event_data}
    except Exception as e:
        error_msg = f"Error in test_insert: {str(e)}"
        frappe.log_error("Goujana Calendar Test Insert Error", error_msg)
        return {"success": False, "message": error_msg}

def insert_event_in_goujana_calendar(doc, method=None):
    """Insert event in Goujana Calendar."""
    if not (doc.custom_sync_with_calendar_provider == 1 
                and doc.custom_calendar_provider == "Goujana Calendar"
                and doc.custom_calendar
                and not doc.custom_calendar_event_id):
        return
    
    calendar_doc = frappe.get_doc("Goujana Calendar", doc.custom_calendar)
    if not calendar_doc:
        frappe.throw(f"Goujana Calendar '{doc.custom_calendar}' not found.")
        
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    
    starts_on = doc.starts_on
    if isinstance(doc.starts_on, str):
        starts_on = frappe.utils.get_datetime(doc.starts_on)
        
    ends_on = doc.ends_on
    if isinstance(doc.ends_on, str):
        ends_on = frappe.utils.get_datetime(doc.ends_on)
    
    event_data = {
        "subject": doc.subject,
        "description": doc.description,
        "starts_on": starts_on.strftime(fmt),
        "ends_on": ends_on.strftime(fmt),
        "custom_goujana_customer_id": doc.custom_goujana_customer_id,
        "custom_calendar_id": doc.custom_calendar_id,
    }

    mapped_data = calendar_doc.map_data_to_push(event_data)
    
    access_token = calendar_doc.access_token
    cookie_value = calendar_doc.cookie_value
    
    if not access_token or not cookie_value:
        frappe.throw("Access Token and Cookie Value are required to push data to Goujana Calendar.")

    headers = {
        "X-API-TOKEN": access_token,
        "Cookie": cookie_value,
        "Content-Type": "application/json"
    }
    
    base_url = "https://goujana.co"
    endpoint = "/api/v1/schedule/appointment/"
    api_url = f"{base_url}{endpoint}"
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=mapped_data,
            timeout=10
        )
        response.raise_for_status()  # Lanza un error si la respuesta no es exitosa (código 2xx)
        
        content = response.json()
        
        # Update doc with the custom_calendar_event_id, in the response is the id field
        # Use direct database update to avoid reloading the document
        frappe.db.set_value("Event", doc.name, "custom_calendar_event_id", content.get("id"))
        frappe.db.commit()
        
    except requests.RequestException as e:
        error_msg = f"Error al enviar evento a Goujana Calendar: {str(e)}"
        frappe.log_error(
            title="Goujana Calendar Event Insert Error",
            message=error_msg,
            doctype="Event",
            docname=doc.name
        )
        frappe.throw(error_msg)
    except Exception as e:
        error_msg = f"Error inesperado al insertar evento en Goujana Calendar: {str(e)}"
        frappe.log_error(
            title="Goujana Calendar Event Insert Error",
            message=error_msg,
            doctype="Event",
            docname=doc.name
        )
        frappe.throw(error_msg)    
    