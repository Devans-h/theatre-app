# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate


def make_test_fixtures():
	"""Create prerequisite Theatre, Movie, Screen for tests."""
	theatre_name = "_Test Theatre Show"
	movie_name = "_Test Movie Show"
	screen_name = "_Test Screen Show"

	if not frappe.db.exists("Theatre", theatre_name):
		frappe.get_doc(
			{"doctype": "Theatre", "theatre_name": theatre_name, "location": "Test City"}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Movie", movie_name):
		frappe.get_doc({
			"doctype": "Movie",
			"movie_name": movie_name,
			"min_ticket_price": 200,
			"max_ticket_price": 500
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("Screen", screen_name):
		frappe.get_doc(
			{
				"doctype": "Screen",
				"screen_name": screen_name,
				"theatre": theatre_name,
				"capacity": 50,
			}
		).insert(ignore_permissions=True)

	# Ensure a valid seat exists for this screen
	seat_num = "_Test Seat Show"
	if not frappe.db.exists("Seat", seat_num):
		frappe.get_doc({
			"doctype": "Seat",
			"seat_number": seat_num,
			"screen": screen_name,
			"price": 300
		}).insert(ignore_permissions=True)

	return theatre_name, movie_name, screen_name


class TestShow(IntegrationTestCase):
	def setUp(self):
		self.theatre, self.movie, self.screen = make_test_fixtures()
		self.today = nowdate()
		# Remove any leftover test shows
		for show in frappe.get_all("Show", filters={"theatre": self.theatre}):
			frappe.delete_doc("Show", show.name, force=True)

	def _make_show(self, show_date=None, start="10:00:00", end="12:00:00",
				   ticket_price=200, status="Scheduled"):
		return frappe.get_doc(
			{
				"doctype": "Show",
				"naming_series": "SHOW-.YYYY.-.####",
				"movie": self.movie,
				"theatre": self.theatre,
				"screen": self.screen,
				"show_date": show_date or self.today,
				"start_time": start,
				"end_time": end,
				"status": status,
			}
		)

	def test_valid_show_creation(self):
		"""A valid show can be created."""
		show = self._make_show()
		show.insert()
		self.assertTrue(frappe.db.exists("Show", show.name))
		frappe.delete_doc("Show", show.name, force=True)

	def test_past_date_rejected(self):
		"""Show date in the past must be rejected."""
		show = self._make_show(show_date=add_days(self.today, -1))
		with self.assertRaises(frappe.ValidationError):
			show.insert()

	def test_invalid_time_rejected(self):
		"""End time before start time must be rejected."""
		show = self._make_show(start="14:00:00", end="12:00:00")
		with self.assertRaises(frappe.ValidationError):
			show.insert()

	def test_seat_price_out_of_bounds_rejected(self):
		"""Show should reject if screen contains seats outside movie price bounds."""
		# Temporarily set seat price out of bounds
		seat = frappe.get_doc("Seat", "_Test Seat Show")
		seat.price = 600
		seat.save(ignore_permissions=True)
		
		show = self._make_show()
		with self.assertRaises(frappe.ValidationError):
			show.insert()
			
		# Restore
		seat.price = 300
		seat.save(ignore_permissions=True)

	def test_screen_not_in_theatre_rejected(self):
		"""Screen belonging to a different theatre must be rejected."""
		# Create another theatre and screen
		other_theatre = "_Test Other Theatre"
		other_screen = "_Test Other Screen"
		if not frappe.db.exists("Theatre", other_theatre):
			frappe.get_doc(
				{"doctype": "Theatre", "theatre_name": other_theatre, "location": "Other City"}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Screen", other_screen):
			frappe.get_doc(
				{
					"doctype": "Screen",
					"screen_name": other_screen,
					"theatre": other_theatre,
					"capacity": 30,
				}
			).insert(ignore_permissions=True)

		show = self._make_show()
		show.screen = other_screen  # wrong theatre's screen
		with self.assertRaises(frappe.ValidationError):
			show.insert()

	def test_overlapping_shows_rejected(self):
		"""Two shows on the same screen/date that overlap must be rejected."""
		show1 = self._make_show(start="18:00:00", end="20:00:00")
		show1.insert()

		show2 = self._make_show(start="19:00:00", end="21:00:00")
		with self.assertRaises(frappe.ValidationError):
			show2.insert()

		frappe.delete_doc("Show", show1.name, force=True)

	def test_adjacent_shows_allowed(self):
		"""Two shows that are adjacent (not overlapping) must be allowed."""
		show1 = self._make_show(start="18:00:00", end="20:00:00")
		show1.insert()

		show2 = self._make_show(start="20:00:00", end="22:00:00")
		show2.insert()  # Should not raise

		frappe.delete_doc("Show", show1.name, force=True)
		frappe.delete_doc("Show", show2.name, force=True)
