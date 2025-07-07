// Copyright (c) 2025, Yeifer and contributors
// For license information, please see license.txt

frappe.ui.form.on('Calendar Hubspot', {
    refresh: function(frm) {
        // Botón Sync HubSpot
        frm.add_custom_button(__('Sync HubSpot'), function() {
            if (!frm.doc.access_token) {
                frappe.msgprint("Please enter an Access Token first.");
                return;
            }
            if (!frm.doc.calendar_id) {
                frappe.msgprint("Please enter a Calendar ID first.");
                return;
            }
            if (!frm.is_dirty() && !frm.docname) {
                frappe.msgprint("Please save the document before syncing.");
                return;
            }
            if (!frm.doc.pull && !frm.doc.push) {
                frappe.msgprint("Neither Pull nor Push is enabled. Enable at least one to sync.");
                return;
            }

            frappe.confirm(
                __('Are you sure you want to sync with HubSpot? This will pull data to HubSpot and then push data from HubSpot.'),
                function() {
                    let current_progress = 0;
                    let maximum_progress = 100;
                    let yield_progress = 90;
                    let time_interval = 200;
                    let finish_time_interval = 1000;
                    let title = __('Syncing with HubSpot');
                    frappe.show_alert({indicator: 'green', message: __(title)});
                    frappe.show_progress(title, current_progress, maximum_progress, 'Please wait');
                    let progress_interval = setInterval(function() {
                        if (current_progress < yield_progress) {
                            current_progress += 1;
                            frappe.show_progress(title, current_progress, maximum_progress, __('Processing: ') + current_progress + '%');
                        }
                    }, time_interval);
                    frappe.call({
                        method: 'any_calendar.any_calendar.doctype.calendar_hubspot.calendar_hubspot.sync_hubspot_data',
                        args: { hubspot_doc: frm.doc.name },
                        callback: function(r) {
                            clearInterval(progress_interval);
                            frappe.show_progress(title, maximum_progress, maximum_progress, __('Synchronization complete!'));
                            setTimeout(function() {
                                frappe.hide_progress();
                                if (r.message) {
                                    frappe.msgprint({
                                        title: __('Sync Completed'),
                                        indicator: 'green',
                                        message: r.message.message || 'Sync completed.'
                                    });
                                }
                            }, finish_time_interval);
                        },
                        error: function(r) {
                            // Detener simulación y mostrar error
                            clearInterval(progress_interval);
                            frappe.show_progress(title , yield_progress, maximum_progress, __('Error occurred during synchronization.'));
                            setTimeout(function() {
                                frappe.hide_progress();
                                frappe.msgprint({
                                    title: __('Error'),
                                    indicator: 'red',
                                    message: 'An error occurred while syncing. Check the logs for details.'
                                });
                            }, finish_time_interval);
                        }
                    });
                }
            );
        });
    },

    usser: function(frm) {
        if (frm.doc.usser && frm.doc.access_token) {
            frm.set_value('access_token', '');  // Borra el token si el usuario cambia
            frappe.msgprint("Access Token cleared due to user change. Please enter a new token.");
        }
    },

    access_token: function(frm) {
        if (frm.doc.access_token) {
            frappe.msgprint("Access Token entered. Use the Sync HubSpot button to proceed.");
        }
    },

    pull: function(frm) {
        if (frm.doc.pull) {
            frappe.msgprint("Pull is enabled. Click 'Sync HubSpot' to fetch data.");
        } else {
            frappe.msgprint("Pull is disabled. Enable it to fetch data from HubSpot.");
        }
    },

    push: function(frm) {
        if (frm.doc.push) {
            frappe.msgprint("Push is enabled. Click 'Sync HubSpot' to send data.");
        } else {
            frappe.msgprint("Push is disabled. Enable it to send data to HubSpot.");
        }
    }
});