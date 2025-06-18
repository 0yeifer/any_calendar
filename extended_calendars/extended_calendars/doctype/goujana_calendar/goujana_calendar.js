// Copyright (c) 2025, Yeifer and contributors
// For license information, please see license.txt

frappe.ui.form.on("Goujana Calendar", {
	refresh(frm) {
        frm.add_custom_button(__("Sync Calendar"), function() {
            if (!frm.doc.access_token) {
                frappe.msgprint(__("Please enter an Access Token first."));
                return;
            }
            if (!frm.doc.cookie_value) {
                frappe.msgprint(__("Please enter a Cookie Value first."));
                return;
            }
            frappe.confirm(
                __('Are you sure you want to synchronize Calendar with GoHighLevel? This will fetch and push events for the specified calendar.'),
                function() {
                    let current_progress = 0;
                    let maximum_progress = 100;
                    let yield_progress = 90;
                    let time_interval = 200;
                    let finish_time_interval = 1000;
                    let title = __("Synchronizing Calendar");
                    frappe.show_alert({indicator: "green", message: __(title)});
                    frappe.show_progress(title, current_progress, maximum_progress, __("Please wait"));
                    let progress_interval = setInterval(function() {
                        if (current_progress < yield_progress) {
                            current_progress += 1;
                            frappe.show_progress(title, current_progress, maximum_progress, __("Processing: ") + current_progress + "%");
                        }
                    }, time_interval);
                    frappe.call({
                        method: "extended_calendars.extended_calendars.doctype.goujana_calendar.goujana_calendar.sync",
                        args: {
                            doc_name: frm.doc.name
                        },
                        callback: function(r) {
                            clearInterval(progress_interval);
                            frappe.show_progress(title, maximum_progress, maximum_progress, __("Synchronization complete!"));
                            setTimeout(function() {
                                frappe.hide_progress();
                                if (r.message && r.message.message) {
                                    let message = r.message.message;
                                    let indicator = r.message.success ? "green" : "orange";
                                    let title = r.message.success ? __("Synchronization Completed") : __("Synchronization Completed with Issues");
                                    
                                    frappe.msgprint({
                                        title: title,
                                        indicator: indicator,
                                        message: message
                                    });
                                } else {
                                    frappe.msgprint({
                                        title: __("Error"),
                                        indicator: "red",
                                        message: __("No valid response received from the API.")
                                    });
                                }
                            }, finish_time_interval);
                        },
                        error: function(r) {
                            clearInterval(progress_interval);
                            frappe.show_progress(title, yield_progress, maximum_progress, __("Error occurred during synchronization."));
                            setTimeout(function() {
                                frappe.hide_progress();
                                frappe.msgprint({
                                    title: __("Error"),
                                    indicator: "red",
                                    message: __("Failed to synchronize Calendar. Please check the error logs.")
                                    });
                            }, finish_time_interval);
                        }
                    });
                },
                function() {
                    frappe.msgprint(__("Calendar synchronization cancelled."));
                }
            )
        });
	},
});
