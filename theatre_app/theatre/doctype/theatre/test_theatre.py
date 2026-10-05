# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests import IntegrationTestCase


class TestTheatre(IntegrationTestCase):
	def setUp(self):
		self.theatre_name = "_Test Theatre"
		# Clean up before each test
		if frappe.db.exists("Theatre", self.theatre_name):
			frappe.delete_doc("Theatre", self.theatre_name, force=True)

	def tearDown(self):
		if frappe.db.exists("Theatre", self.theatre_name):
			frappe.delete_doc("Theatre", self.theatre_name, force=True)

	def test_theatre_creation(self):
		"""Theatre can be created with required fields."""
		theatre = frappe.get_doc(
			{
				"doctype": "Theatre",
				"theatre_name": self.theatre_name,
				"location": "Test Location",
			}
		)
		theatre.insert()
		self.assertTrue(frappe.db.exists("Theatre", self.theatre_name))

	def test_theatre_requires_name(self):
		"""Theatre requires theatre_name."""
		theatre = frappe.get_doc(
			{
				"doctype": "Theatre",
				"location": "Test Location",
			}
		)
		with self.assertRaises(Exception):
			theatre.insert()

	def test_theatre_requires_location(self):
		"""Theatre requires location."""
		theatre = frappe.get_doc(
			{
				"doctype": "Theatre",
				"theatre_name": self.theatre_name,
			}
		)
		with self.assertRaises(Exception):
			theatre.insert()
