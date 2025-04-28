# Copyright (c) 2025, Yeifer and contributors
# For license information, please see license.txt

import frappe
import requests
import json
import time
import logging
import pytz
import re
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from functools import wraps

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Clase GHLCalendar
class GHLCalendar(Document):
    def get_config(self):
        """Obtiene configuración del doctype GHL Calendar."""
        if not all([self.location_id, self.access_token, self.calendar_id]):
            frappe.throw(_("Los campos location_id, access_token y calendar_id son requeridos"))
        return {"location_id": self.location_id, "access_token": self.access_token, "calendar_id": self.calendar_id}

def with_ghl_config(func):
    """Decorador para obtener configuración de GHL Calendar y añadir depuración."""
    @wraps(func)
    def wrapper(doc_name=None, *args, **kwargs):
        config = get_ghl_config(doc_name)
        logger.info(f"Configuración obtenida: location_id={config['location_id']}, calendar_id={config['calendar_id']}")
        return func(config, doc_name=doc_name, *args, **kwargs)
    return wrapper

@frappe.whitelist()
def pull_ghl_data(doc_name=None):
    """Fetch event data from GoHighLevel and create/update events in Frappe's Event Doctype."""
    logger.info(f"Iniciando pull_ghl_data para GHL Calendar: {doc_name}")
    doc = frappe.get_doc("GHL Calendar", doc_name)
    if not doc.pull:
        logger.warning("Pull está deshabilitado")
        return {"success": False, "message": "Pull is disabled."}
    
    # Sincronizar contactos y obtener caché
    logger.info("Sincronizando contactos y generando caché antes de obtener eventos")
    contacts_cache = fetch_contacts(doc_name=doc_name)  # Obtener todos los contactos
    # Crear un diccionario para búsqueda rápida por contactId
    contacts_cache_by_id = {contact["id"]: contact for contact in contacts_cache if contact["id"]}
    logger.info(f"Caché de contactos generado con {len(contacts_cache_by_id)} entradas")
    # Log para contactos sin teléfono
    logger.info(f"Contactos sin teléfono en caché: {sum(1 for c in contacts_cache if not c.get('phone'))}")
    
    config = doc.get_config()
    calendar_id = config["calendar_id"]
    
    # Obtener eventos
    start_date, end_date = get_default_date_range()
    events_data = fetch_calendar_events(doc_name=doc_name, start_date=start_date, end_date=end_date)
    events = events_data.get("events", [])
    
    stats = {"total_events": 0, "created_count": 0, "updated_count": 0, "skipped_count": 0}
    
    try:
        stats["total_events"] = len(events)
        logger.info(f"Procesando {stats['total_events']} eventos")
        
        for event in events:
            event_id = event.get("id")
            if not event_id:
                stats["skipped_count"] += 1
                logger.warning("Omitiendo evento sin ID")
                continue
                
            # Verificar si el evento ya existe
            event_info = frappe.db.get_value(
                "Event",
                {"custom_calendar_event_id": event_id},
                ["name", "custom_sync_with_calendar_provider", "custom_client_name", "custom_contact_phone"],
                as_dict=True
            )
            if event_info and event_info.get("custom_sync_with_calendar_provider") != 1:
                stats["skipped_count"] += 1
                logger.warning(f"Omitiendo evento {event_id}: sincronización deshabilitada")
                continue
                
            # Mapear datos del evento
            start_time_raw = event.get("startTime", "1970-01-01T00:00:00+00:00")
            end_time_raw = event.get("endTime", "1970-01-01T00:00:00+00:00")
            logger.info(f"Evento {event_id}: startTime original={start_time_raw}, endTime original={end_time_raw}")

            bogota_tz = pytz.timezone("America/Bogota")
            try:
                start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00")).astimezone(bogota_tz)
                end_time = datetime.fromisoformat(end_time_raw.replace("Z", "+00:00")).astimezone(bogota_tz)
            except ValueError as e:
                stats["skipped_count"] += 1
                logger.error(f"Error al convertir fechas para evento {event_id}: {str(e)}")
                continue
            logger.info(f"Evento {event_id}: startTime convertido a Bogota={start_time.isoformat()}, endTime convertido a Bogota={end_time.isoformat()}")

            # Inicializar event_data con los datos de GHL
            event_data = {
                "subject": event.get("title", "Evento GHL"),
                "starts_on": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "ends_on": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "description": event.get("notes", ""),
                "custom_pulled_from_calendar_provider": 1  # Siempre establecer este campo
            }
            
            # Campos personalizados (solo para creación)
            custom_data = {
                "custom_calendar_event_id": event_id,
                "custom_calendar_provider": "GHL Calendar",
                "custom_ghl_calendar_id": calendar_id,
                "custom_pulled_from_calendar_provider": 1,
                "custom_calendar": doc_name,
                "custom_sync_with_calendar_provider": 1
            }
            
            # Manejar participantes
            contact_id = event.get("contactId")
            if contact_id:
                logger.info(f"Buscando contacto {contact_id} en caché para evento {event_id}")
                contact_data = contacts_cache_by_id.get(contact_id)
                
                if not contact_data:
                    logger.warning(f"Contacto {contact_id} no encontrado en caché para evento {event_id}")
                    # Preservar valores existentes en Frappe si el evento ya existe
                    event_data["custom_client_name"] = event_info.get("custom_client_name", "") if event_info else ""
                    event_data["custom_contact_phone"] = event_info.get("custom_contact_phone", "") if event_info else ""
                else:
                    # Asignar datos del contacto desde GHL
                    event_data["custom_client_name"] = contact_data.get("firstName", "") or ""
                    event_data["custom_contact_phone"] = str(contact_data.get("phone", "")) or ""
                    logger.info(f"Evento {event_id}: asignado nombre={event_data['custom_client_name']}, teléfono={event_data['custom_contact_phone']}")
            else:
                logger.info(f"Evento {event_id} sin contactId asociado")
                # Preservar valores existentes en Frappe si el evento ya existe
                event_data["custom_client_name"] = event_info.get("custom_client_name", "") if event_info else ""
                event_data["custom_contact_phone"] = event_info.get("custom_contact_phone", "") if event_info else ""
            
            # Crear o actualizar evento
            if event_info:
                logger.info(f"Actualizando evento existente: {event_id}")
                event = frappe.get_doc("Event", event_info["name"])
                event.update(event_data)  # Sobrescribir con datos de GHL, preservando custom_client_name y custom_contact_phone si no hay contacto
                event.save(ignore_permissions=True)
                stats["updated_count"] += 1
            else:
                logger.info(f"Creando nuevo evento: {event_id}")
                event_data.update(custom_data)  # Agregar campos personalizados para nuevos eventos
                event = frappe.get_doc({"doctype": "Event", **event_data})
                event.insert(ignore_permissions=True)
                stats["created_count"] += 1
            
            time.sleep(0.1)
        
        frappe.db.commit()
        message = f"Procesados {stats['total_events']} eventos: {stats['created_count']} creados, {stats['updated_count']} actualizados, {stats['skipped_count']} omitidos"
        logger.info(message)
        return {"success": True, "message": message, "stats": stats}
    
    except Exception as e:
        logger.error(f"Error en pull_ghl_data: {str(e)}")
        frappe.log_error(f"Error en pull: {str(e)}", "GHL Pull Error")
        return {"success": False, "message": f"Error en pull: {str(e)}"}

@frappe.whitelist()
@with_ghl_config
def push_ghl_data(config, doc_name=None):
    """Push events to GoHighLevel."""
    doc = frappe.get_doc("GHL Calendar", doc_name)
    if not doc.push:
        return {"success": False, "message": "Push está deshabilitado", "stats": {}}

    # Obtener contactos
    try:
        contacts_cache = fetch_contacts(doc_name=doc_name)
    except Exception as e:
        return {"success": False, "message": f"Error obteniendo contactos: {str(e)}", "stats": {}}

    # Obtener eventos de Frappe
    events = frappe.get_all(
        "Event",
        filters={
            "custom_calendar_provider": "GHL Calendar",
            "custom_sync_with_calendar_provider": 1,
            "custom_calendar": doc_name
        },
        fields=["name", "subject", "description", "starts_on", "ends_on", "custom_calendar_event_id", "custom_client_name", "custom_contact_phone"]
    )

    # Obtener eventos existentes en GHL para caché
    try:
        start_date, end_date = get_default_date_range()
        events_data = fetch_calendar_events(doc_name=doc_name, start_date=start_date, end_date=end_date)
        existing_event_ids = {event.get("id") for event in events_data.get("events", []) if event.get("id")}
        logger.info(f"Caché de eventos existentes en GHL generado con {len(existing_event_ids)} IDs")
    except Exception as e:
        logger.error(f"Error obteniendo eventos de GHL para caché: {str(e)}")
        return {"success": False, "message": f"Error obteniendo eventos de GHL: {str(e)}", "stats": {}}

    stats = {"total": len(events), "success": 0, "skipped": 0}

    # Obtener user_id para el calendario
    user_id = get_user_id_from_calendar(config)
    logger.info(f"User ID para el calendario {config['calendar_id']}: {user_id}")

    for event in events:
        event_name = event["name"]
        try:
            # Obtener fechas como strings locales
            starts_on = event["starts_on"].strftime("%Y-%m-%d %H:%M:%S")
            ends_on = event["ends_on"].strftime("%Y-%m-%d %H:%M:%S")
            
            # Convertir a formato GHL (añadir T y offset -05:00)
            start_time_ghl = f"{starts_on.replace(' ', 'T')}-05:00"
            end_time_ghl = f"{ends_on.replace(' ', 'T')}-05:00"

            contact_id = None
            # Crear o buscar contacto en GHL usando custom_client_name y custom_contact_phone
            if event.get("custom_client_name") and event.get("custom_contact_phone"):
                contact_data = {
                    "firstName": event["custom_client_name"],
                    "phone": event["custom_contact_phone"],
                    "locationId": config["location_id"],
                    "assignedTo": user_id  # Asignar el user_id al contacto
                }
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Version": "2021-07-28"
                }
                # Validar datos del contacto
                if not contact_data["firstName"].strip() or not contact_data["phone"].strip():
                    logger.warning(f"Datos de contacto inválidos para evento {event_name}: nombre={contact_data['firstName']}, teléfono={contact_data['phone']}")
                    stats["skipped"] += 1
                    continue

                # Buscar contacto existente por teléfono
                response = make_api_request(
                    "/contacts/",
                    config["access_token"],
                    method="GET",
                    params={"query": event["custom_contact_phone"], "locationId": config["location_id"]},
                    headers=headers
                )
                contacts = response.get("contacts", [])
                if contacts:
                    contact_id = contacts[0].get("id")
                    # Actualizar contacto existente
                    response = make_api_request(
                        f"/contacts/{contact_id}",
                        config["access_token"],
                        method="PUT",
                        json_data=contact_data,
                        headers=headers
                    )
                    logger.info(f"Contacto actualizado para evento {event_name}: ID={contact_id}, assignedTo={user_id}")
                else:
                    # Crear nuevo contacto
                    response = make_api_request(
                        "/contacts/",
                        config["access_token"],
                        method="POST",
                        json_data=contact_data,
                        headers=headers
                    )
                    contact_id = response.get("contact", {}).get("id")
                    if contact_id:
                        logger.info(f"Contacto creado para evento {event_name}: ID={contact_id}, assignedTo={user_id}")
                    else:
                        logger.error(f"No se pudo crear contacto para evento {event_name}")
                        stats["skipped"] += 1
                        continue
            else:
                logger.warning(f"Evento {event_name} sin custom_client_name o custom_contact_phone")
                stats["skipped"] += 1
                continue

            event_data = {
                "title": event.get("subject", "Evento GHL"),
                "appointmentStatus": "new",
                "assignedUserId": user_id,
                "ignoreFreeSlotValidation": True,
                "calendarId": config["calendar_id"],
                "locationId": config["location_id"],
                "startTime": start_time_ghl,
                "endTime": end_time_ghl,
                "contactId": contact_id if contact_id else "",
                "notes": event.get("description", "")
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Version": "2021-04-15"
            }

            event_id = event.get("custom_calendar_event_id")
            if event_id and event_id in existing_event_ids:
                endpoint = f"/calendars/events/appointments/{event_id}"
                method = "PUT"
            else:
                endpoint = "/calendars/events/appointments"
                method = "POST"

            response = make_api_request(
                endpoint,
                config["access_token"],
                method=method,
                json_data=event_data,
                headers=headers
            )

            if response.get("error"):
                logger.error(f"Error en evento {event_name}: {response.get('error')}")
                stats["skipped"] += 1
                continue

            if method == "POST":
                new_event_id = response.get("id") or response.get("appointment", {}).get("id")
                if new_event_id:
                    frappe.db.set_value(
                        "Event",
                        event_name,
                        {
                            "custom_calendar_event_id": new_event_id,
                            "custom_pulled_from_calendar_provider": 0
                        }
                    )
                    logger.info(f"Evento {event_name} actualizado con ID GHL: {new_event_id}")
                else:
                    logger.error(f"No se pudo obtener ID del evento creado en GHL para {event_name}")
                    stats["skipped"] += 1
                    continue

            stats["success"] += 1

        except Exception as e:
            stats["skipped"] += 1
            logger.error(f"Error en evento {event_name}: {str(e)}", exc_info=True)

    frappe.db.commit()
    return {
        "success": stats["success"] > 0,
        "message": f"Exitosos: {stats['success']}, Omitidos: {stats['skipped']}",
        "stats": stats
    }

@frappe.whitelist()
def update_ghl_calendar(doc_name=None, event_id=None, title=None, start_time=None, end_time=None, notes=None, contact_id=None, custom_client_name=None, custom_contact_phone=None):
    """Update a specific event in GoHighLevel."""
    logger.info(f"Iniciando update_ghl_calendar para evento {event_id} en GHL Calendar: {doc_name}")
    doc = frappe.get_doc("GHL Calendar", doc_name)
    config = doc.get_config()
    access_token = config["access_token"]
    calendar_id = config["calendar_id"]
    location_id = config["location_id"]
    
    try:
        # Obtener eventos existentes en GHL para caché
        start_date, end_date = get_default_date_range()
        events_data = fetch_calendar_events(doc_name=doc_name, start_date=start_date, end_date=end_date)
        existing_event_ids = {event.get("id") for event in events_data.get("events", []) if event.get("id")}
        logger.info(f"Caché de eventos existentes en GHL generado con {len(existing_event_ids)} IDs")

        # Verificar si el evento existe usando el caché
        if event_id not in existing_event_ids:
            logger.error(f"Evento {event_id} no existe en GHL")
            return {"success": False, "message": f"Evento {event_id} no existe en GHL"}
        
        # Manejar contacto si se proporcionan custom_client_name y custom_contact_phone
        if custom_client_name and custom_contact_phone:
            contact_data = {
                "firstName": custom_client_name,
                "phone": custom_contact_phone,
                "locationId": location_id
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Version": "2021-07-28"
            }
            # Buscar contacto existente por teléfono
            response = make_api_request(
                "/contacts/",
                access_token,
                method="GET",
                params={"query": custom_contact_phone, "locationId": location_id},
                headers=headers
            )
            contacts = response.get("contacts", [])
            if contacts:
                contact_id = contacts[0].get("id")
                # Actualizar contacto
                make_api_request(
                    f"/contacts/{contact_id}",
                    access_token,
                    method="PUT",
                    json_data=contact_data,
                    headers=headers
                )
            else:
                # Crear nuevo contacto
                response = make_api_request(
                    "/contacts/",
                    access_token,
                    method="POST",
                    json_data=contact_data,
                    headers=headers
                )
                contact_id = response.get("contact", {}).get("id")
            logger.info(f"Contacto para evento {event_id}: ID={contact_id}")

        # Preparar datos para actualización
        event_data = {
            "calendarId": calendar_id,
            "locationId": location_id,
            "appointmentStatus": "confirmed"
        }
        
        if start_time:
            start_time_ghl = f"{start_time.replace(' ', 'T')}-05:00"
            event_data["startTime"] = start_time_ghl
            
        if end_time:
            end_time_ghl = f"{end_time.replace(' ', 'T')}-05:00"
            event_data["endTime"] = end_time_ghl

        if title:
            event_data["title"] = title
        if notes:
            event_data["notes"] = notes
        if contact_id:
            event_data["contactId"] = contact_id
        
        logger.info(f"Actualizando evento {event_id} con datos: {event_data}")
        response = make_api_request(
            f"/calendars/events/appointments/{event_id}",
            access_token,
            method="PUT",
            json_data=event_data,
            headers={"Version": "2021-04-15"}
        )
        
        if response.get("error"):
            logger.error(f"Error al actualizar evento {event_id}: {response.get('error')}")
            return {"success": False, "message": f"Error al actualizar evento: {response.get('error')}"}
        
        logger.info(f"Evento {event_id} actualizado exitosamente en GHL")
        return {"success": True, "message": f"Evento {event_id} actualizado exitosamente"}
    
    except Exception as e:
        logger.error(f"Error al actualizar evento {event_id}: {str(e)}")
        frappe.log_error(f"Error al actualizar evento {event_id}: {str(e)}", "GHL Update Error")
        return {"success": False, "message": f"Error al actualizar evento {event_id}: {str(e)}"}

# Funciones de sincronización
@frappe.whitelist()
def sync_ghl_data(doc_name=None):
    """Sincronización completa con manejo mejorado de errores."""
    try:
        doc = frappe.get_doc("GHL Calendar", doc_name)
        pull_result = {"success": False, "message": "Pull skipped (disabled)", "stats": {}}
        push_result = {"success": False, "message": "Push skipped (disabled)", "stats": {}}

        if doc.pull:
            pull_result = pull_ghl_data(doc_name)
            if not pull_result.get("success"):
                frappe.log_error(f"Pull failed: {pull_result.get('message')}", "GHL Sync Error")

        if doc.push:
            push_result = push_ghl_data(doc_name)
            if not push_result.get("success") and push_result["stats"].get("total", 0) > 0:
                frappe.log_error(f"Push failed: {push_result.get('message')}", "GHL Sync Error")

        combined_message = format_sync_results(pull_result, push_result)
        success = (
            (pull_result.get("success", False) or not doc.pull) and
            (push_result.get("success", False) or not doc.push)
        )
        return {
            "success": success,
            "message": combined_message,
            "pull_result": pull_result,
            "push_result": push_result
        }

    except Exception as e:
        error_msg = f"Error en sync_ghl_data: {str(e)}"
        frappe.log_error(error_msg, "GHL Sync Error")
        return {"success": False, "message": error_msg}
    
def format_sync_results(pull_result, push_result):
    """Formatea los resultados de pull y push en un mensaje combinado."""
    pull_msg = pull_result.get("message", "No se realizó pull")
    push_msg = push_result.get("message", "No se realizó push")
    return f"Resultados de sincronización:\n- Pull: {pull_msg}\n- Push: {push_msg}"

# Otras funciones utilitarias
def get_ghl_config(doc_name=None):
    """Obtiene configuración de GHL Calendar desde un documento."""
    logger.info(f"Obteniendo configuración para GHL Calendar: {doc_name or 'primer documento'}")
    doc = frappe.get_doc("GHL Calendar", doc_name or frappe.get_all("GHL Calendar", limit=1)[0].name)
    return doc.get_config()

def get_default_date_range(timezone="America/New_York"):
    """Calcula fechas por defecto: 3 días antes, 6 meses después."""
    tz = pytz.timezone(timezone)
    start = datetime.now(tz) - timedelta(days=3)
    end = datetime.now(tz) + relativedelta(months=6)
    return str(int(start.timestamp() * 1000)), str(int(end.timestamp() * 1000))

def build_api_params(config, **kwargs):
    """Construye parámetros para solicitudes API."""
    return {"locationId": config["location_id"], **kwargs}

def fetch_paginated_data(config, endpoint, params, headers=None):
    """Obtiene datos paginados de un endpoint."""
    results = []
    page = 1
    limit = params.get("limit", 100)
    
    logger.info(f"Iniciando paginación para endpoint: {endpoint}")
    while True:
        params["page"] = page
        response = make_api_request(endpoint, config["access_token"], params=params, headers=headers)
        
        contacts = response.get("contacts") or []
        results.extend({
            "id": c.get("id", ""),
            "firstName": c.get("firstName", ""),
            "phone": c.get("phone", "")
        } for c in contacts if c.get("phone"))
        
        logger.info(f"Página {page}: {len(contacts)} contactos obtenidos")
        if len(contacts) < limit:
            break
        page += 1
    
    logger.info(f"Total contactos obtenidos: {len(results)}")
    return results

@frappe.whitelist()
@with_ghl_config
def fetch_calendar_events(config, doc_name=None, start_date=None, end_date=None):
    """Obtiene eventos de calendario sin paginación."""
    logger.info("Iniciando obtención de eventos de calendario")
    start_date, end_date = start_date or get_default_date_range()[0], end_date or get_default_date_range()[1]
    
    # Validar calendarId
    logger.info(f"Validando calendarId: {config['calendar_id']}")
    try:
        calendar_response = make_api_request(f"/calendars/{config['calendar_id']}", config["access_token"])
        if not calendar_response.get("calendar"):
            logger.error(f"calendarId {config['calendar_id']} no válido o no encontrado")
            frappe.throw(_("El calendarId {0} no es válido o no está disponible").format(config["calendar_id"]))
    except requests.RequestException as e:
        logger.error(f"Error al validar calendarId {config['calendar_id']}: {str(e)}")
        frappe.throw(_("Error al validar calendarId {0}: {1}").format(config["calendar_id"], str(e)))
    
    params = build_api_params(config, calendarId=config["calendar_id"], startTime=start_date, endTime=end_date)
    try:
        response = make_api_request("/calendars/events", config["access_token"], params=params)
        events = response.get("events", [])
        logger.info(f"Total eventos obtenidos: {len(events)}")
        return {"events": events}
    except requests.RequestException as e:
        if hasattr(e, 'response') and e.response:
            logger.error(f"Error al obtener eventos: Código {e.response.status_code}, Detalle: {e.response.text}")
            frappe.throw(_("Error al obtener eventos: Código {0}, Detalle: {1}").format(e.response.status_code, e.response.text))
        raise

@frappe.whitelist()
@with_ghl_config
def fetch_contacts(config, doc_name=None, limit=100):
    """Obtiene contactos filtrados por userId."""
    user_id = get_user_id_from_calendar(config)
    params = build_api_params(config, assignedTo=user_id)
    return fetch_paginated_data(config, "/contacts/", params, headers={"Version": "2021-07-28"})

@frappe.whitelist()
def sync_contacts(doc_name=None):
    """Sincroniza contactos desde GHL a doctype Contact."""
    logger.info(f"Iniciando sincronización de contactos para GHL Calendar: {doc_name}")
    contacts = fetch_contacts(doc_name=doc_name)
    created, updated, skipped = 0, 0, 0
    
    for contact in contacts:
        if not contact["phone"]:
            logger.warning(f"Omitiendo contacto sin teléfono: {contact['firstName']}")
            skipped += 1
            continue
        
        # Buscar contacto existente en Frappe por teléfono
        contact_exists = frappe.db.exists("Contact", {"phone": contact["phone"]})
        
        contact_data = {
            "first_name": contact["firstName"],
            "phone": contact["phone"]
        }
        
        if contact_exists:
            # Actualizar contacto existente
            frappe.db.set_value("Contact", {"phone": contact["phone"]}, contact_data)
            updated += 1
            logger.info(f"Contacto actualizado: {contact['phone']}")
        else:
            # Crear nuevo contacto
            new_contact = frappe.get_doc({
                "doctype": "Contact",
                **contact_data
            })
            new_contact.insert(ignore_permissions=True)
            created += 1
            logger.info(f"Contacto creado: {contact['phone']}")
    
    frappe.db.commit()
    result = {"created": created, "updated": updated, "skipped": skipped}
    logger.info(f"Sincronización de contactos completada: {result}")
    return result

def get_headers(access_token):
    """Devuelve las cabeceras estándar para solicitudes a GHL."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": "2021-04-15"
    }

def get_user_id_from_calendar(config):
    """Obtiene userId desde un calendarId."""
    logger.info(f"Obteniendo userId para calendarId: {config['calendar_id']}")
    response = make_api_request(f"/calendars/{config['calendar_id']}", config["access_token"])
    if "calendar" not in response or not response["calendar"].get("teamMembers"):
        logger.error(f"No se encontraron teamMembers para el calendario {config['calendar_id']}")
        frappe.throw(_("No se encontraron teamMembers para el calendario {0}").format(config['calendar_id']))
    
    user_id = response["calendar"]["teamMembers"][0].get("userId")
    if not user_id:
        logger.error(f"No se encontró userId para el calendario {config['calendar_id']}")
        frappe.throw(_("No se encontró userId para el calendario {0}").format(config['calendar_id']))
    
    logger.info(f"userId encontrado: {user_id}")
    return user_id

def make_api_request(endpoint, access_token, method="GET", json_data=None, params=None, headers=None):
    """Realiza una solicitud a la API de GoHighLevel."""
    default_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": "2021-04-15"
    }
    if headers:
        default_headers.update(headers)
    
    url = f"https://services.leadconnectorhq.com{endpoint}"
    try:
        logger.info(f"Solicitando {method} {url}")
        response = requests.request(
            method,
            url,
            headers=default_headers,
            json=json_data,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        content = response.json()
        logger.info(f"Respuesta: {response.status_code}, Contenido: {content}")
        return content
    except requests.exceptions.RequestException as e:
        # Inicializar valores por defecto
        status_code = 0
        error_msg = str(e)
        content = {}
        
        # Si hay una respuesta, extraer detalles
        if 'response' in locals() and response is not None:
            status_code = response.status_code
            error_msg = f"{status_code} Client Error: {response.reason} for url: {url}"
            try:
                content = response.json()
            except ValueError:
                content = {"raw_response": response.text}
        
        # Registrar el error
        logger.error(f"Error en API: {{'error': '{error_msg}', 'url': '{url}', 'status_code': {status_code}, 'response': {json.dumps(content)}}}")
        return {"error": error_msg, "status": status_code}

def normalize_phone(phone):
    """Normaliza un número de teléfono eliminando caracteres no numéricos, manteniendo el código de país."""
    if not phone:
        return ""
    # Mantener solo dígitos y el signo '+' (para códigos de país)
    return re.sub(r'[^\d+]', '', phone)

def create_or_update_ghl_contact(event, access_token, location_id, user_id, headers):
    """Crea o actualiza un contacto en GHL y lo asigna al user_id, buscando por número de teléfono."""
    if not event.custom_client_name or not event.custom_contact_phone:
        logger.warning(f"Evento {event.name} sin custom_client_name o custom_contact_phone válidos")
        return None

    # Normalizar el número de teléfono ingresado
    raw_phone = event.custom_contact_phone.strip()
    normalized_phone = normalize_phone(raw_phone)

    contact_data = {
        "firstName": event.custom_client_name.strip(),
        "phone": raw_phone,  # Mantener el formato original para la API
        "locationId": location_id,
        "assignedTo": user_id
    }

    # Validar datos del contacto
    if not contact_data["firstName"] or not normalized_phone:
        logger.warning(f"Datos de contacto inválidos para evento {event.name}: nombre={contact_data['firstName']}, teléfono={contact_data['phone']}")
        return None

    # Buscar contacto existente por número de teléfono
    response = make_api_request(
        "/contacts/",
        access_token,
        method="GET",
        params={"query": raw_phone, "locationId": location_id},
        headers={"Version": "2021-07-28"}
    )
    contacts = response.get("contacts", [])
    
    # Filtrar contactos para coincidencia de subcadena con el número normalizado
    matching_contacts = [
        contact for contact in contacts
        if normalized_phone in normalize_phone(contact.get("phone", ""))
        and len(normalize_phone(contact.get("phone", ""))) >= len(normalized_phone)
    ]

    if matching_contacts:
        contact = matching_contacts[0]
        contact_id = contact.get("id")
        current_assigned_to = contact.get("assignedTo", "")
        
        # Verificar si el assignedTo cambió
        if current_assigned_to and current_assigned_to != user_id:
            logger.warning(f"Cambio de usuario asignado para contacto {contact_id} (teléfono: {contact_data['phone']}): de {current_assigned_to} a {user_id}")

        # Actualizar contacto existente con firstName, phone y assignedTo
        update_data = {
            "firstName": contact_data["firstName"],
            "phone": contact_data["phone"],
            "assignedTo": user_id
        }
        response = make_api_request(
            f"/contacts/{contact_id}",
            access_token,
            method="PUT",
            json_data=update_data,
            headers={"Version": "2021-07-28"}
        )
        if response.get("error"):
            logger.error(f"Error actualizando contacto {contact_id} para evento {event.name}: {response['error']}")
            return None
        logger.info(f"Contacto actualizado para evento {event.name}: ID={contact_id}, assignedTo={user_id}")
        return contact_id
    else:
        # Crear nuevo contacto
        response = make_api_request(
            "/contacts/",
            access_token,
            method="POST",
            json_data=contact_data,
            headers={"Version": "2021-07-28"}
        )
        contact_id = response.get("contact", {}).get("id")
        if contact_id:
            logger.info(f"Contacto creado para evento {event.name}: ID={contact_id}, assignedTo={user_id}")
            return contact_id
        else:
            logger.error(f"No se pudo crear contacto para evento {event.name}: {response.get('error', 'Sin ID')}")
            return None

def insert_event_in_ghl_calendar(doc, method=None):
    """Insert event in GHL calendar."""
    try:
        if not (doc.custom_sync_with_calendar_provider == 1 
                and doc.custom_calendar_provider == "GHL Calendar" 
                and doc.custom_calendar
                and not doc.custom_calendar_event_id):
            logger.info(f"Evento {doc.name} no cumple criterios para inserción en GHL")
            return

        calendar = frappe.get_doc("GHL Calendar", doc.custom_calendar)
        config = {"access_token": calendar.access_token, "calendar_id": calendar.calendar_id, "location_id": calendar.location_id}
        
        # Validar configuración
        if not all([config["access_token"], config["calendar_id"], config["location_id"]]):
            frappe.throw(_("Los campos access_token, calendar_id y location_id son requeridos en GHL Calendar"))

        # Obtener user_id
        user_id = get_user_id_from_calendar(config)
        
        # Crear o actualizar contacto
        contact_id = create_or_update_ghl_contact(doc, config["access_token"], config["location_id"], user_id, get_headers(config["access_token"]))
        
        # Convertir fechas a datetime
        logger.info(f"Evento {doc.name}: starts_on={doc.starts_on}, ends_on={doc.ends_on}")
        try:
            starts_on = frappe.utils.get_datetime(doc.starts_on)
            ends_on = frappe.utils.get_datetime(doc.ends_on)
        except Exception as e:
            logger.error(f"Error convirtiendo fechas para evento {doc.name}: {str(e)}")
            frappe.throw(_("Error convirtiendo fechas del evento: {0}").format(str(e)))

        # Preparar datos del evento
        start_time_ghl = starts_on.strftime("%Y-%m-%dT%H:%M:%S-05:00")
        end_time_ghl = ends_on.strftime("%Y-%m-%dT%H:%M:%S-05:00")
        title = doc.subject or "Evento GHL"
        cleaned_title = " ".join(title.split())
        print(f"cleaned_title: {cleaned_title}")
        event_data = {
            "title": cleaned_title,
            "appointmentStatus": "new",
            "assignedUserId": user_id,
            "ignoreFreeSlotValidation": True,
            "calendarId": config["calendar_id"],
            "locationId": config["location_id"],
            "startTime": start_time_ghl,
            "endTime": end_time_ghl,
            "contactId": contact_id or "",
            "notes": doc.description or ""
        }

        # Insertar evento en GHL
        response = make_api_request(
            "/calendars/events/appointments",
            config["access_token"],
            method="POST",
            json_data=event_data,
            headers=get_headers(config["access_token"])
        )

        if response.get("error"):
            logger.error(f"Error insertando evento {doc.name} en GHL: {response['error']}")
            frappe.msgprint(_("Error insertando evento en GHL: {0}").format(response["error"]))
            return

        meeting_id = response.get("id") or response.get("appointment", {}).get("id")
        if meeting_id:
            doc.custom_calendar_event_id = meeting_id
            doc.custom_pulled_from_calendar_provider = 0
            doc.db_update()
            frappe.db.commit()
            logger.info(f"Evento {doc.name} insertado en GHL con ID: {meeting_id}")
            frappe.msgprint(_("Evento insertado exitosamente en GHL con ID: {0}").format(meeting_id))
        else:
            logger.error(f"No se obtuvo ID del evento creado para {doc.name}")
            frappe.msgprint(_("Error: No se obtuvo ID del evento creado en GHL"))

    except frappe.DoesNotExistError:
        logger.error(f"Documento {doc.name} no existe")
        frappe.msgprint(_("Error: Documento {0} no existe").format(doc.name))
    except Exception as e:
        logger.error(f"Error insertando evento {doc.name} en GHL: {str(e)}")
        frappe.msgprint(_("Error insertando evento en GHL: {0}").format(str(e)))

def update_event_in_ghl_calendar(doc, method=None):
    """Update event in GHL calendar."""
    try:
        if not (doc.custom_sync_with_calendar_provider == 1 
                and doc.custom_calendar_provider == "GHL Calendar" 
                and doc.custom_calendar
                and doc.custom_calendar_event_id):
            logger.info(f"Evento {doc.name} no cumple criterios para actualización en GHL")
            return

        calendar = frappe.get_doc("GHL Calendar", doc.custom_calendar)
        config = {"access_token": calendar.access_token, "calendar_id": calendar.calendar_id, "location_id": calendar.location_id}
        
        # Validar configuración
        if not all([config["access_token"], config["calendar_id"], config["location_id"]]):
            frappe.throw(_("Los campos access_token, calendar_id y location_id son requeridos en GHL Calendar"))

        # Obtener user_id
        user_id = get_user_id_from_calendar(config)
        
        # Crear o actualizar contacto
        contact_id = create_or_update_ghl_contact(doc, config["access_token"], config["location_id"], user_id, get_headers(config["access_token"]))
        
        # Convertir fechas a datetime
        logger.info(f"Evento {doc.name}: starts_on={doc.starts_on}, ends_on={doc.ends_on}")
        try:
            starts_on = frappe.utils.get_datetime(doc.starts_on)
            ends_on = frappe.utils.get_datetime(doc.ends_on)
        except Exception as e:
            logger.error(f"Error convirtiendo fechas para evento {doc.name}: {str(e)}")
            frappe.throw(_("Error convirtiendo fechas del evento: {0}").format(str(e)))

        # Preparar datos del evento
        start_time_ghl = starts_on.strftime("%Y-%m-%dT%H:%M:%S-05:00")
        end_time_ghl = ends_on.strftime("%Y-%m-%dT%H:%M:%S-05:00")

        title = doc.subject or "Evento GHL"
        cleaned_title = " ".join(title.split())
        print(f"cleaned_title: {cleaned_title}")
        event_data = {
            "title": cleaned_title,
            "appointmentStatus": "confirmed",
            "assignedUserId": user_id,
            "calendarId": config["calendar_id"],
            "locationId": config["location_id"],
            "startTime": start_time_ghl,
            "endTime": end_time_ghl,
            "contactId": contact_id or "",
            "notes": doc.description or ""
        }

        # Actualizar evento en GHL
        response = make_api_request(
            f"/calendars/events/appointments/{doc.custom_calendar_event_id}",
            config["access_token"],
            method="PUT",
            json_data=event_data,
            headers=get_headers(config["access_token"])
        )

        if response.get("error"):
            logger.error(f"Error actualizando evento {doc.name} en GHL: {response['error']}")
            frappe.msgprint(_("Error actualizando evento en GHL: {0}").format(response["error"]))
            return

        logger.info(f"Evento {doc.name} actualizado en GHL con ID: {doc.custom_calendar_event_id}")

    except frappe.DoesNotExistError:
        logger.error(f"Documento {doc.name} no existe")
        frappe.msgprint(_("Error: Documento {0} no existe").format(doc.name))
    except Exception as e:
        logger.error(f"Error actualizando evento {doc.name} en GHL: {str(e)}")
        frappe.msgprint(_("Error actualizando evento en GHL: {0}").format(str(e)))

def delete_event_in_ghl_calendar(doc, method=None):
    """Delete event in GHL calendar."""
    try:
        if not (doc.custom_sync_with_calendar_provider == 1 
                and doc.custom_calendar_provider == "GHL Calendar" 
                and doc.custom_calendar
                and doc.custom_calendar_event_id):
            logger.info(f"Evento {doc.name} no cumple criterios para eliminación en GHL")
            return

        calendar = frappe.get_doc("GHL Calendar", doc.custom_calendar)
        config = {"access_token": calendar.access_token, "calendar_id": calendar.calendar_id}
        
        # Validar configuración
        if not all([config["access_token"], config["calendar_id"]]):
            frappe.throw(_("Los campos access_token y calendar_id son requeridos en GHL Calendar"))

        # Eliminar evento en GHL
        response = make_api_request(
            f"/calendars/events/{doc.custom_calendar_event_id}",
            config["access_token"],
            method="DELETE",
            headers=get_headers(config["access_token"])
        )

        if response.get("error"):
            logger.error(f"Error eliminando evento {doc.name} en GHL: {response['error']}")
            frappe.msgprint(_("Error eliminando evento en GHL: {0}").format(response["error"]))
            return

        logger.info(f"Evento {doc.name} eliminado en GHL con ID: {doc.custom_calendar_event_id}")

    except frappe.DoesNotExistError:
        logger.error(f"Documento {doc.name} no existe")
        frappe.msgprint(_("Error: Documento {0} no existe").format(doc.name))
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de solicitud eliminando evento {doc.name} en GHL: {str(e)}")
        frappe.msgprint(_("Error de solicitud eliminando evento en GHL: {0}").format(str(e)))
    except Exception as e:
        logger.error(f"Error eliminando evento {doc.name} en GHL: {str(e)}")
        frappe.msgprint(_("Error eliminando evento en GHL: {0}").format(str(e)))