// Copyright (c) 2026, Devansh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Show", {
	refresh(frm) {
		// Show today's date by default for new shows
		if (frm.is_new() && !frm.doc.show_date) {
			frm.set_value("show_date", frappe.datetime.get_today());
		}
	},

	theatre(frm) {
		// Filter screens to those belonging to selected theatre
		frm.set_query("screen", function () {
			return {
				filters: { theatre: frm.doc.theatre },
			};
		});
		frm.set_value("screen", "");
	},

	movie(frm) {
		if (frm.doc.movie) {
			// Auto-suggest end time based on movie duration
			frappe.db
				.get_value("Movie", frm.doc.movie, "duration")
				.then(function (r) {
					if (r.message && r.message.duration && frm.doc.start_time) {
						// Duration is in seconds, calculate end time
						let start = frappe.datetime.str_to_obj(
							frappe.datetime.get_today() + " " + frm.doc.start_time
						);
						let end = new Date(start.getTime() + r.message.duration * 1000);
						frm.set_value(
							"end_time",
							end.getHours() +
								":" +
								String(end.getMinutes()).padStart(2, "0") +
								":00"
						);
					}
				});
		}
	},

	show_date(frm) {
		// Warn user if show date is in the past
		if (frm.doc.show_date) {
			let today = frappe.datetime.get_today();
			if (frm.doc.show_date < today) {
				frappe.msgprint({
					title: __("Warning"),
					message: __("Show date is in the past. The server will reject this."),
					indicator: "orange",
				});
			}
		}
	},
});
