import frappe
import requests
from urllib.parse import quote
from frappe.integrations.google_oauth import GoogleOAuth
from frappe.integrations.doctype.google_calendar.google_calendar import (
    update_event_in_calendar as original_update_event_in_calendar,
    get_google_calendar_object as original_get_google_calendar_object,
)
from frappe.utils import get_request_site_address
from frappe.integrations.doctype.google_calendar.google_calendar import get_authentication_url

def update_event_in_calendar(account, event, recurrence=None):
    event = frappe.get_doc("Event", {"google_calendar_event_id": event.get("id")})
    if (event and event.sync_with_google_calendar == 1):
        original_update_event_in_calendar(account, event, recurrence)
    else:
        return
    
def get_google_calendar_object(g_calendar):
    try:
        google_calendar, account = original_get_google_calendar_object(g_calendar)
    except Exception as e:
        account = frappe._dict()
        account.push_to_google_calendar = None
        google_calendar = None
        frappe.log_error(f"Error fetching Google Calendar object: {str(e)}")
    return google_calendar, account

### Original code
#@frappe.whitelist()
#def authorize_access(g_calendar, reauthorize=None):
#	"""
#	If no Authorization code get it from Google and then request for Refresh Token.
#	Google Calendar Name is set to flags to set_value after Authorization Code is obtained.
#	"""
#	google_settings = frappe.get_doc("Google Settings")
#	google_calendar = frappe.get_doc("Google Calendar", g_calendar)
#	google_calendar.check_permission("write")
#
#	redirect_uri = (
#		get_request_site_address(True)
#		+ "?cmd=frappe.integrations.doctype.google_calendar.google_calendar.google_callback"
#	)
#
#	if not google_calendar.authorization_code or reauthorize:
#		frappe.cache.hset("google_calendar", "google_calendar", google_calendar.name)
#		return get_authentication_url(client_id=google_settings.client_id, redirect_uri=redirect_uri)
#	else:
#		try:
#			data = {
#				"code": google_calendar.get_password(fieldname="authorization_code", raise_exception=False),
#				"client_id": google_settings.client_id,
#				"client_secret": google_settings.get_password(
#					fieldname="client_secret", raise_exception=False
#				),
#				"redirect_uri": redirect_uri,
#				"grant_type": "authorization_code",
#			}
#			r = requests.post(GoogleOAuth.OAUTH_URL, data=data).json()
#
#			if "refresh_token" in r:
#				frappe.db.set_value(
#					"Google Calendar", google_calendar.name, "refresh_token", r.get("refresh_token")
#				)
#				frappe.db.commit()
#
#			frappe.local.response["type"] = "redirect"
#			frappe.local.response["location"] = "/app/Form/{}/{}".format(
#				quote("Google Calendar"), quote(google_calendar.name)
#			)
#
#			frappe.msgprint(_("Google Calendar has been configured."))
#		except Exception as e:
#			frappe.throw(e)

@frappe.whitelist()
def authorize_access(g_calendar, reauthorize=None, redirect_location=None):
    """
    If no Authorization code get it from Google and then request for Refresh Token.
    Google Calendar Name is set to flags to set_value after Authorization Code is obtained.
    """
    google_settings = frappe.get_doc("Google Settings")
    google_calendar = frappe.get_doc("Google Calendar", g_calendar)
    google_calendar.check_permission("write")

    redirect_uri = (
        get_request_site_address(True)
        + "?cmd=frappe.integrations.doctype.google_calendar.google_calendar.google_callback"
    )

    if not google_calendar.authorization_code or reauthorize:
        frappe.cache.hset("google_calendar", "google_calendar", google_calendar.name)
        if redirect_location: frappe.cache.hset("google_calendar", "redirect_location", redirect_location)
        return get_authentication_url(client_id=google_settings.client_id, redirect_uri=redirect_uri)
    else:
        try:
            data = {
                "code": google_calendar.get_password(fieldname="authorization_code", raise_exception=False),
                "client_id": google_settings.client_id,
                "client_secret": google_settings.get_password(
                    fieldname="client_secret", raise_exception=False
                ),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            r = requests.post(GoogleOAuth.OAUTH_URL, data=data).json()

            if "refresh_token" in r:
                frappe.db.set_value(
                    "Google Calendar", google_calendar.name, "refresh_token", r.get("refresh_token")
                )
                frappe.db.commit()

            if not redirect_location:
                redirect_location = frappe.cache.hget("google_calendar", "redirect_location")
            if not redirect_location:
                redirect_location = "/app/Form/{}/{}".format(
                    quote("Google Calendar"), quote(google_calendar.name)
                )
            
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = redirect_location
            
            frappe.msgprint(_("Google Calendar has been configured."))
        except Exception as e:
            frappe.throw(e)

@frappe.whitelist(allow_guest=True)
def google_callback(code=None):
    """
    Authorization code is sent to callback as per the API configuration
    """

    print(frappe.session.sid)
    
    frappe.local.cookie_manager.set_cookie

    google_calendar = frappe.cache.hget("google_calendar", "google_calendar")
    frappe.db.set_value("Google Calendar", google_calendar, "authorization_code", code)
    frappe.db.commit()
    
    authorize_access(google_calendar)
