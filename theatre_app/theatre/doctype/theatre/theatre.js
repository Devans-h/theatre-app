// Copyright (c) 2026, Devansh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Theatre", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Refresh Shows"), function () {
				frm.call("refresh_shows").then(() => {
					frm.reload_doc();
					frappe.msgprint(__("Shows refreshed."));
				});
			});
		}
	},
});
