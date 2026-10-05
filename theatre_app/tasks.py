# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt
"""
Scheduled background tasks for theatre_app.
"""

import frappe


def expire_reservations():
	"""
	Called every minute by Frappe scheduler.
	Marks Reserved bookings whose reservation_expires_at has passed as Expired.
	"""
	from frappe.utils import now_datetime
	expired_count = frappe.db.sql(
		"""
		UPDATE `tabBooking`
		SET status = 'Expired', modified = %(now)s, modified_by = 'Administrator'
		WHERE status = 'Reserved'
		  AND reservation_expires_at IS NOT NULL
		  AND reservation_expires_at < %(now)s
		""",
		{"now": now_datetime()}
	)
	if frappe.db.affected_rows():
		frappe.logger("theatre_app").info(
			f"Expired {frappe.db.affected_rows()} stale booking reservations."
		)
