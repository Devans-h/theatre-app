# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt
import frappe
from frappe.tests import IntegrationTestCase


class TestSeat(IntegrationTestCase):
	def test_seat_price_must_be_positive(self):
		seat = frappe.get_doc({
			"doctype": "Seat",
			"seat_number": "_Test Seat Price",
			"screen": "_Test Screen",
			"price": 0
		})
		with self.assertRaises(frappe.ValidationError):
			seat.insert(ignore_permissions=True)
