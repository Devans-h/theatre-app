# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, now_datetime, nowdate

from theatre_app.theatre.doctype.booking.booking import (
	confirm_booking,
	reserve_seats,
)


def make_booking_fixtures():
	"""Set up Theatre, Movie, Screen, Seats, Customer, Show."""
	theatre_name = "_Test Theatre Booking"
	movie_name = "_Test Movie Booking"
	screen_name = "_Test Screen Booking"
	customer_name = "_Test Customer Booking"

	if not frappe.db.exists("Theatre", theatre_name):
		frappe.get_doc(
			{"doctype": "Theatre", "theatre_name": theatre_name, "location": "Booking City"}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Movie", movie_name):
		frappe.get_doc({
			"doctype": "Movie",
			"movie_name": movie_name,
			"min_ticket_price": 100,
			"max_ticket_price": 500
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("Screen", screen_name):
		frappe.get_doc(
			{
				"doctype": "Screen",
				"screen_name": screen_name,
				"theatre": theatre_name,
				"capacity": 10,
			}
		).insert(ignore_permissions=True)

	prices = [150, 200, 250]
	for i, seat_num in enumerate(["BA1", "BA2", "BA3"]):
		if not frappe.db.exists("Seat", seat_num):
			frappe.get_doc(
				{
					"doctype": "Seat",
					"seat_number": seat_num,
					"screen": screen_name,
					"row": "A",
					"seat_type": "Regular",
					"price": prices[i]
				}
			).insert(ignore_permissions=True)

	# Ensure customer exists
	if not frappe.db.exists("Customer", customer_name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": customer_name,
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
			}
		).insert(ignore_permissions=True)

	return theatre_name, movie_name, screen_name, customer_name


def make_test_show(theatre, movie, screen, show_date=None):
	show = frappe.get_doc(
		{
			"doctype": "Show",
			"naming_series": "SHOW-.YYYY.-.####",
			"movie": movie,
			"theatre": theatre,
			"screen": screen,
			"show_date": show_date or nowdate(),
			"start_time": "15:00:00",
			"end_time": "17:00:00",
			"status": "Scheduled",
		}
	)
	show.insert(ignore_permissions=True)
	return show


class TestBooking(IntegrationTestCase):
	def setUp(self):
		self.theatre, self.movie, self.screen, self.customer = make_booking_fixtures()
		self.show = make_test_show(self.theatre, self.movie, self.screen)
		self.seat_a1 = "BA1"
		self.seat_a2 = "BA2"
		self.seat_a3 = "BA3"
		# Clean up all bookings for this show
		for b in frappe.get_all("Booking", filters={"show": self.show.name}):
			frappe.delete_doc("Booking", b.name, force=True)

	def tearDown(self):
		# Clean up bookings, tickets, then show
		for t in frappe.get_all("Ticket", filters={"show": self.show.name}):
			frappe.delete_doc("Ticket", t.name, force=True)
		for b in frappe.get_all("Booking", filters={"show": self.show.name}):
			frappe.delete_doc("Booking", b.name, force=True)
		if frappe.db.exists("Show", self.show.name):
			frappe.delete_doc("Show", self.show.name, force=True)

	def test_valid_reservation(self):
		"""A seat can be reserved successfully and prices are summed."""
		result = reserve_seats(
			show=self.show.name,
			seat_ids=self.seat_a1,
			customer=self.customer,
		)
		self.assertIn("booking", result)
		booking = frappe.get_doc("Booking", result["booking"])
		self.assertEqual(booking.status, "Reserved")
		self.assertEqual(booking.subtotal, 150) # BA1 is 150

	def test_no_seats_rejected(self):
		"""Reservation with no seats must fail."""
		with self.assertRaises(Exception):
			reserve_seats(show=self.show.name, seat_ids="", customer=self.customer)

	def test_double_reservation_rejected(self):
		"""Second user cannot reserve the same seat while first holds it."""
		reserve_seats(show=self.show.name, seat_ids=self.seat_a1, customer=self.customer)
		# Second attempt for same seat must fail
		with self.assertRaises(frappe.ValidationError):
			reserve_seats(show=self.show.name, seat_ids=self.seat_a1, customer=self.customer)

	def test_past_show_rejected(self):
		"""Cannot book a show with a past date."""
		# Create a past show directly in DB to bypass server validation
		past_show = frappe.get_doc(
			{
				"doctype": "Show",
				"naming_series": "SHOW-.YYYY.-.####",
				"movie": self.movie,
				"theatre": self.theatre,
				"screen": self.screen,
				"show_date": nowdate(),  # today — we'll manually set it to past
				"start_time": "10:00:00",
				"end_time": "12:00:00",
				"ticket_price": 200,
				"status": "Scheduled",
			}
		)
		past_show.insert(ignore_permissions=True)
		# Manually set to past
		frappe.db.set_value("Show", past_show.name, "show_date", add_days(nowdate(), -1))

		with self.assertRaises(frappe.ValidationError):
			reserve_seats(
				show=past_show.name, seat_ids=self.seat_a1, customer=self.customer
			)

		frappe.delete_doc("Show", past_show.name, force=True)

	def test_successful_confirmation_creates_tickets(self):
		"""Confirming a booking creates one ticket per seat."""
		result = reserve_seats(
			show=self.show.name,
			seat_ids=",".join([self.seat_a1, self.seat_a2, self.seat_a3]),
			customer=self.customer,
		)
		booking_name = result["booking"]
		confirm_result = confirm_booking(booking_name=booking_name)

		self.assertEqual(confirm_result["status"], "Confirmed")

		# Subtotal should be 150 + 200 + 250 = 600
		booking = frappe.get_doc("Booking", booking_name)
		self.assertEqual(booking.subtotal, 600)

		# Verify 3 tickets created with correct prices
		tickets = frappe.get_all(
			"Ticket", filters={"booking": booking_name}, fields=["name", "seat", "price"]
		)
		self.assertEqual(len(tickets), 3)
		seat_map = {t.seat: t.price for t in tickets}
		self.assertEqual(seat_map[self.seat_a1], 150)
		self.assertEqual(seat_map[self.seat_a2], 200)
		self.assertEqual(seat_map[self.seat_a3], 250)

	def test_expired_reservation_handled(self):
		"""An expired reservation is rejected on confirmation."""
		result = reserve_seats(
			show=self.show.name, seat_ids=self.seat_a1, customer=self.customer
		)
		booking_name = result["booking"]
		# Manually expire the reservation
		frappe.db.set_value(
			"Booking",
			booking_name,
			"reservation_expires_at",
			add_to_date(now_datetime(), minutes=-1),
		)
		with self.assertRaises(frappe.ValidationError):
			confirm_booking(booking_name=booking_name)

	def test_already_confirmed_seat_rejected(self):
		"""Cannot reserve a seat that is already confirmed."""
		# Reserve and confirm A1
		r1 = reserve_seats(
			show=self.show.name, seat_ids=self.seat_a1, customer=self.customer
		)
		confirm_booking(booking_name=r1["booking"])

		# Now try to reserve A1 again
		with self.assertRaises(frappe.ValidationError):
			reserve_seats(
				show=self.show.name, seat_ids=self.seat_a1, customer=self.customer
			)


class TestCoupon(IntegrationTestCase):
	def setUp(self):
		from frappe.utils import nowdate
		self.coupon_code = "_TEST-COUPON"
		if frappe.db.exists("Coupon", self.coupon_code):
			frappe.delete_doc("Coupon", self.coupon_code, force=True)

	def tearDown(self):
		if frappe.db.exists("Coupon", self.coupon_code):
			frappe.delete_doc("Coupon", self.coupon_code, force=True)

	def _make_coupon(self, **kwargs):
		defaults = {
			"doctype": "Coupon",
			"coupon_code": self.coupon_code,
			"discount_type": "Percentage",
			"discount_value": 10,
			"enabled": 1,
		}
		defaults.update(kwargs)
		c = frappe.get_doc(defaults)
		c.insert(ignore_permissions=True)
		return c

	def test_valid_coupon(self):
		from theatre_app.theatre.doctype.coupon.coupon import validate_coupon
		self._make_coupon()
		result = validate_coupon(self.coupon_code, 1000)
		self.assertEqual(result["discount_amount"], 100)  # 10% of 1000

	def test_disabled_coupon_rejected(self):
		from theatre_app.theatre.doctype.coupon.coupon import validate_coupon
		self._make_coupon(enabled=0)
		with self.assertRaises(frappe.ValidationError):
			validate_coupon(self.coupon_code, 1000)

	def test_expired_coupon_rejected(self):
		from theatre_app.theatre.doctype.coupon.coupon import validate_coupon
		self._make_coupon(valid_until=add_days(nowdate(), -1))
		with self.assertRaises(frappe.ValidationError):
			validate_coupon(self.coupon_code, 1000)

	def test_future_coupon_rejected(self):
		from theatre_app.theatre.doctype.coupon.coupon import validate_coupon
		self._make_coupon(valid_from=add_days(nowdate(), 5))
		with self.assertRaises(frappe.ValidationError):
			validate_coupon(self.coupon_code, 1000)

	def test_usage_limit_exceeded_rejected(self):
		from theatre_app.theatre.doctype.coupon.coupon import validate_coupon
		self._make_coupon(usage_limit=2, used_count=2)
		with self.assertRaises(frappe.ValidationError):
			validate_coupon(self.coupon_code, 1000)





class TestScreen(IntegrationTestCase):
	def test_screen_capacity_must_be_positive(self):
		"""Screen capacity <= 0 must be rejected."""
		theatre = frappe.get_all("Theatre", limit=1, fields=["name"])
		if not theatre:
			frappe.get_doc(
				{"doctype": "Theatre", "theatre_name": "_Cap Test Theatre", "location": "X"}
			).insert(ignore_permissions=True)
			theatre_name = "_Cap Test Theatre"
		else:
			theatre_name = theatre[0].name

		screen = frappe.get_doc(
			{
				"doctype": "Screen",
				"screen_name": "_Test Cap Screen",
				"theatre": theatre_name,
				"capacity": 0,
			}
		)
		with self.assertRaises(frappe.ValidationError):
			screen.insert(ignore_permissions=True)

	def test_duplicate_seat_rejected(self):
		"""Same seat number on same screen must be rejected."""
		theatre = frappe.get_all("Theatre", limit=1, fields=["name"])[0].name
		screen_name = "_Test Dup Seat Screen"
		if not frappe.db.exists("Screen", screen_name):
			frappe.get_doc(
				{
					"doctype": "Screen",
					"screen_name": screen_name,
					"theatre": theatre,
					"capacity": 5,
				}
			).insert(ignore_permissions=True)

		seat_name = "_Test Dup Seat"
		if frappe.db.exists("Seat", seat_name):
			frappe.delete_doc("Seat", seat_name, force=True)

		frappe.get_doc(
			{
				"doctype": "Seat",
				"seat_number": seat_name,
				"screen": screen_name,
			}
		).insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Seat",
					"seat_number": seat_name,  # duplicate
					"screen": screen_name,
				}
			).insert(ignore_permissions=True)

		frappe.delete_doc("Seat", seat_name, force=True)
		frappe.delete_doc("Screen", screen_name, force=True)
