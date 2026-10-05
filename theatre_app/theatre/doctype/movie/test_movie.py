# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase


class TestMovie(IntegrationTestCase):
	def setUp(self):
		self.movie_name = "_Test Movie"
		if frappe.db.exists("Movie", self.movie_name):
			frappe.delete_doc("Movie", self.movie_name, force=True)

	def tearDown(self):
		if frappe.db.exists("Movie", self.movie_name):
			frappe.delete_doc("Movie", self.movie_name, force=True)

	def test_movie_creation(self):
		"""Movie can be created with a movie_name."""
		movie = frappe.get_doc(
			{
				"doctype": "Movie",
				"movie_name": self.movie_name,
				"description": "A test movie",
				"min_ticket_price": 500,
				"max_ticket_price": 800,
			}
		)
		movie.insert()
		self.assertTrue(frappe.db.exists("Movie", self.movie_name))

	def test_movie_requires_name(self):
		"""Movie insertion fails without movie_name."""
		movie = frappe.get_doc({
			"doctype": "Movie",
			"description": "A test movie",
			"min_ticket_price": 500,
			"max_ticket_price": 800
		})
		with self.assertRaises(Exception):
			movie.insert()

	def test_min_price_must_be_positive(self):
		movie = frappe.get_doc({
			"doctype": "Movie",
			"movie_name": self.movie_name,
			"min_ticket_price": 0,
			"max_ticket_price": 800
		})
		with self.assertRaises(frappe.ValidationError):
			movie.insert()

	def test_max_price_must_be_positive(self):
		movie = frappe.get_doc({
			"doctype": "Movie",
			"movie_name": self.movie_name,
			"min_ticket_price": 500,
			"max_ticket_price": -100
		})
		with self.assertRaises(frappe.ValidationError):
			movie.insert()

	def test_min_less_than_max(self):
		movie = frappe.get_doc({
			"doctype": "Movie",
			"movie_name": self.movie_name,
			"min_ticket_price": 800,
			"max_ticket_price": 500
		})
		with self.assertRaises(frappe.ValidationError):
			movie.insert()
