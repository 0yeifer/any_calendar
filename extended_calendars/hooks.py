app_name = "extended_calendars"
app_title = "Any Calendar"
app_publisher = "Yeifer"
app_description = "Syncing and managing events from any calendar provider"
app_email = "developer@yeifer.co"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "any_calendar",
# 		"logo": "/assets/any_calendar/logo.png",
# 		"title": "Any Calendar",
# 		"route": "/any_calendar",
# 		"has_permission": "any_calendar.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/any_calendar/css/any_calendar.css"
# app_include_js = "/assets/any_calendar/js/any_calendar.js"

# include js, css files in header of web template
# web_include_css = "/assets/any_calendar/css/any_calendar.css"
# web_include_js = "/assets/any_calendar/js/any_calendar.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "any_calendar/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}

doctype_js = {
    "Event": "public/js/override/custom_event.js",
}

# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "any_calendar/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "any_calendar.utils.jinja_methods",
# 	"filters": "any_calendar.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "any_calendar.install.before_install"
# after_install = "any_calendar.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "any_calendar.uninstall.before_uninstall"
# after_uninstall = "any_calendar.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "any_calendar.utils.before_app_install"
# after_app_install = "any_calendar.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "any_calendar.utils.before_app_uninstall"
# after_app_uninstall = "any_calendar.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "any_calendar.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

override_doctype_class = {
    "Event": "extended_calendars.overrides.event.custom_event.CustomEvent",
    "Contact": "extended_calendars.overrides.contact.custom_contact.CustomContact"
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

doc_events = {
    "Event": {
        "after_insert": "extended_calendars.utils.insert_event_in_calendar_provider",
        "on_update": "extended_calendars.utils.update_event_in_calendar_provider",
        "on_trash": "extended_calendars.utils.delete_event_in_calendar_provider",
    }
}

# /workspace/development/frappe-bench/apps/any_calendar/any_calendar/any_calendar/doctype/calendar_hubspot/calendar_hubspot.py
# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"any_calendar.tasks.all"
# 	],
# 	"daily": [
# 		"any_calendar.tasks.daily"
# 	],
# 	"hourly": [
# 		"any_calendar.tasks.hourly"
# 	],
# 	"weekly": [
# 		"any_calendar.tasks.weekly"
# 	],
# 	"monthly": [
# 		"any_calendar.tasks.monthly"
# 	],
# }

scheduler_events = {
    "cron": {
        "* * * * *": [
            "extended_calendars.extended_calendars.doctype.goujana_calendar.goujana_calendar.sync_all_goujana_calendars"
        ]
    }
}

# Testing
# -------

# before_tests = "any_calendar.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "any_calendar.event.get_events"
# }
override_whitelisted_methods = {
	"frappe.integrations.doctype.google_calendar.google_calendar.authorize_access": "extended_calendars.overrides.google_calendar.custom_google_calendar.authorize_access",
    "frappe.integrations.doctype.google_calendar.google_calendar.google_callback": "extended_calendars.overrides.google_calendar.custom_google_calendar.google_callback",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "any_calendar.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["any_calendar.utils.before_request"]
# after_request = ["any_calendar.utils.after_request"]

# Job Events
# ----------
# before_job = ["any_calendar.utils.before_job"]
# after_job = ["any_calendar.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"any_calendar.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

