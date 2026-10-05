// Copyright (c) 2026, Devansh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Screen", {
	refresh(frm) {
		// Filter seats by this screen
		if (!frm.is_new()) {
			frm.add_custom_button(__("View Seats"), function () {
				frappe.set_route("List", "Seat", { screen: frm.doc.name });
			});
		}
	},
});
