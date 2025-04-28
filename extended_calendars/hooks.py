app_name = "extended_calendars"
app_title = "Extended Calendars"
app_publisher = "Yeifer"
app_description = "Extended Calendars Hubsptot, GHL y google calendars"
app_email = "developer@yeifer.co"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "extended_calendars",
# 		"logo": "/assets/extended_calendars/logo.png",
# 		"title": "Extended Calendars",
# 		"route": "/extended_calendars",
# 		"has_permission": "extended_calendars.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/extended_calendars/css/extended_calendars.css"
# app_include_js = "/assets/extended_calendars/js/extended_calendars.js"

# include js, css files in header of web template
# web_include_css = "/assets/extended_calendars/css/extended_calendars.css"
# web_include_js = "/assets/extended_calendars/js/extended_calendars.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "extended_calendars/public/scss/website"

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
# app_include_icons = "extended_calendars/public/icons.svg"

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
# 	"methods": "extended_calendars.utils.jinja_methods",
# 	"filters": "extended_calendars.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "extended_calendars.install.before_install"
# after_install = "extended_calendars.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "extended_calendars.uninstall.before_uninstall"
# after_uninstall = "extended_calendars.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "extended_calendars.utils.before_app_install"
# after_app_install = "extended_calendars.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "extended_calendars.utils.before_app_uninstall"
# after_app_uninstall = "extended_calendars.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "extended_calendars.notifications.get_notification_config"

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

# /workspace/development/frappe-bench/apps/extended_calendars/extended_calendars/extended_calendars/doctype/calendar_hubspot/calendar_hubspot.py
# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"extended_calendars.tasks.all"
# 	],
# 	"daily": [
# 		"extended_calendars.tasks.daily"
# 	],
# 	"hourly": [
# 		"extended_calendars.tasks.hourly"
# 	],
# 	"weekly": [
# 		"extended_calendars.tasks.weekly"
# 	],
# 	"monthly": [
# 		"extended_calendars.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "extended_calendars.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "extended_calendars.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "extended_calendars.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["extended_calendars.utils.before_request"]
# after_request = ["extended_calendars.utils.after_request"]

# Job Events
# ----------
# before_job = ["extended_calendars.utils.before_job"]
# after_job = ["extended_calendars.utils.after_job"]

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
# 	"extended_calendars.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

