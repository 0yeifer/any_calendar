// Copyright (c) 2025, Yeifer and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Calendar Hubspot", {
// 	refresh(frm) {

// 	},
// });

// Copyright (c) 2025, Yeifer and contributors
// For license information, please see license.txt

frappe.ui.form.on('Calendar Hubspot', {
    refresh: function(frm) {
        // Botón Pull
        frm.add_custom_button(__('Pull from HubSpot'), function() {
            if (!frm.doc.access_token) {
                frappe.msgprint("Please enter an Access Token first.");
                return;
            }
            if (!frm.is_dirty() && !frm.docname) {
                frappe.msgprint("Please save the document before pulling data.");
                return;
            }
            frappe.show_alert({indicator: 'green', message: __('Pulling data...')});
            frappe.call({
                method: 'extended_calendars.extended_calendars.doctype.calendar_hubspot.calendar_hubspot.pull_hubspot_data',
                args: { hubspot_doc: frm.doc.name },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                },
                error: function(r) {
                    frappe.msgprint("An error occurred while pulling data. Check the logs for details.");
                }
            });
        });

        // Botón Push
        frm.add_custom_button(__('Push to HubSpot'), function() {
            if (!frm.doc.access_token) {
                frappe.msgprint("Please enter an Access Token first.");
                return;
            }
            if (!frm.is_dirty() && !frm.docname) {
                frappe.msgprint("Please save the document before pushing data.");
                return;
            }
            frappe.show_alert({indicator: 'green', message: __('Pushing data...')});
            frappe.call({
                method: 'extended_calendars.extended_calendars.doctype.calendar_hubspot.calendar_hubspot.push_hubspot_data',
                args: { hubspot_doc: frm.doc.name },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                },
                error: function(r) {
                    frappe.msgprint("An error occurred while pushing data. Check the logs for details.");
                }
            });
        });
    },
    usser: function(frm) {
        if (frm.doc.usser && frm.doc.access_token) {
            frm.set_value('access_token', '');  // Borra el token si el usuario cambia
        }
    },
    access_token: function(frm) {
        if (frm.doc.access_token) {
            frappe.msgprint("Access Token entered. Use the Pull or Push buttons to proceed.");
        }
    },
    pull: function(frm) {
        if (frm.doc.pull) {
            frappe.msgprint("Pull is enabled. Click 'Pull from HubSpot' to fetch data.");
        }
    },
    push: function(frm) {
        if (frm.doc.push) {
            frappe.msgprint("Push is enabled. Click 'Push to HubSpot' to send data.");
        }
    }
});