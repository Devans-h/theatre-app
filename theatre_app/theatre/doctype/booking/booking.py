# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, getdate, nowdate, now_datetime

from theatre_app.theatre.doctype.coupon.coupon import validate_coupon

# Default tax rate (can be configured or fetched from ERPNext template)
DEFAULT_TAX_RATE = 0.0  # Set to e.g. 0.18 for 18% GST


class Booking(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from theatre_app.theatre.doctype.booking_seat.booking_seat import BookingSeat

		coupon: DF.Link | None
		customer: DF.Link
		discount: DF.Currency
		grand_total: DF.Currency
		naming_series: DF.Literal["BOOK-.YYYY.-.####"]
		reservation_expires_at: DF.Datetime | None
		sales_invoice: DF.Link | None
		seats: DF.Table[BookingSeat]
		show: DF.Link
		status: DF.Literal["Reserved", "Confirmed", "Expired", "Cancelled"]
		subtotal: DF.Currency
		tax: DF.Currency
	# end: auto-generated types

	def validate(self):
		"""Basic sanity checks on save."""
		if self.status != "Cancelled":
			self._populate_seat_prices()

		if self.status == "Reserved" and not self.reservation_expires_at:
			self.reservation_expires_at = add_to_date(now_datetime(), minutes=10)

		if self.status == "Confirmed":
			self._validate_show_is_bookable()
			self._validate_seats_not_empty()

	def _populate_seat_prices(self):
		if not self.show or not self.seats:
			return
		
		seat_ids = [s.seat for s in self.seats if s.seat]
		if not seat_ids:
			return

		seat_records = frappe.get_all("Seat", filters={"name": ["in", seat_ids]}, fields=["name", "price"])
		seat_map = {s.name: (s.price or 0) for s in seat_records}

		subtotal = 0.0
		for row in self.seats:
			# If the price is zero/empty, or this is a brand new booking, fetch from Seat.
			# (Protects against client-side tampering and read-only field stripping)
			if not row.price or self.is_new():
				row.price = seat_map.get(row.seat, 0)
			subtotal += (row.price or 0)
		
		self.subtotal = subtotal
		
		# Recalculate grand total
		discount = self.discount or 0
		after_discount = self.subtotal - discount
		tax = after_discount * DEFAULT_TAX_RATE
		self.tax = tax
		self.grand_total = max(after_discount + tax, 0)



	def _validate_show_is_bookable(self):
		show = frappe.get_doc("Show", self.show)
		if show.status != "Scheduled":
			frappe.throw(_("Show {0} is not in Scheduled status.").format(self.show))
		if getdate(show.show_date) < getdate(nowdate()):
			frappe.throw(_("Cannot book a show that is in the past."))

	def _validate_seats_not_empty(self):
		if not self.seats:
			frappe.throw(_("At least one seat must be selected."))


# ---------------------------------------------------------------------------
# Whitelisted API methods
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_available_seats(show: str) -> list:
	"""
	Return all seats for the show's screen with their availability status.
	Status: Available | Reserved | Booked
	"""
	show_doc = frappe.get_doc("Show", show)
	screen = show_doc.screen

	# All seats for this screen
	all_seats = frappe.get_all(
		"Seat",
		filters={"screen": screen},
		fields=["name", "seat_number", "row", "seat_type", "price"],
		order_by="row asc, seat_number asc",
	)

	# Expire stale reservations before querying
	_expire_stale_reservations()

	# Get confirmed booked seats for this show
	confirmed_seats = _get_seats_by_status(show, "Confirmed")
	# Get actively reserved seats for this show (not expired)
	reserved_seats = _get_active_reserved_seats(show)

	confirmed_set = set(confirmed_seats)
	reserved_set = set(reserved_seats)

	result = []
	for seat in all_seats:
		if seat.name in confirmed_set:
			status = "Booked"
		elif seat.name in reserved_set:
			status = "Reserved"
		else:
			status = "Available"
		result.append(
			{
				"seat": seat.name,
				"seat_number": seat.seat_number,
				"row": seat.row,
				"seat_type": seat.seat_type,
				"price": seat.price,
				"status": status,
			}
		)
	return result


@frappe.whitelist()
def reserve_seats(show: str, seat_ids: str, customer: str, coupon_code: str = "") -> dict:
	"""
	Reserve seats for a show. Creates a Booking in Reserved status.
	Uses database-level locking to prevent double-booking.

	seat_ids: comma-separated seat names
	Returns: booking name and expiry
	"""
	import json

	# seat_ids can be JSON array or comma-separated
	if seat_ids.startswith("["):
		seats = json.loads(seat_ids)
	else:
		seats = [s.strip() for s in seat_ids.split(",") if s.strip()]

	if not seats:
		frappe.throw(_("No seats selected."))

	show_doc = frappe.get_doc("Show", show)

	# --- Server-side validations ---
	if show_doc.status != "Scheduled":
		frappe.throw(_("Show is not available for booking."))
	if getdate(show_doc.show_date) < getdate(nowdate()):
		frappe.throw(_("Cannot book a past show."))

	# Validate all seats belong to the show's screen
	for seat_id in seats:
		seat_screen = frappe.get_value("Seat", seat_id, "screen")
		if seat_screen != show_doc.screen:
			frappe.throw(
				_("Seat {0} does not belong to the screen for this show.").format(seat_id)
			)

	# Expire stale reservations
	_expire_stale_reservations()

	# Use a database-level approach: acquire a lock within a transaction
	# to prevent race conditions. We use frappe.db.sql with FOR UPDATE.
	try:
		frappe.db.begin()

		# Lock existing booking_seat rows for this show to prevent concurrent inserts
		# This uses raw SQL with FOR UPDATE — justified for concurrency correctness
		for seat_id in seats:
			# Check if seat is confirmed for this show
			confirmed = frappe.db.sql(
				"""
				SELECT bs.name
				FROM `tabBooking Seat` bs
				INNER JOIN `tabBooking` b ON b.name = bs.parent
				WHERE b.show = %(show)s
				  AND bs.seat = %(seat)s
				  AND b.status = 'Confirmed'
				LIMIT 1 FOR UPDATE
				""",
				{"show": show, "seat": seat_id},
			)
			if confirmed:
				frappe.db.rollback()
				frappe.throw(
					_("Seat {0} is already confirmed for this show.").format(seat_id)
				)

			# Check if seat is actively reserved by another booking
			reserved = frappe.db.sql(
				"""
				SELECT bs.name
				FROM `tabBooking Seat` bs
				INNER JOIN `tabBooking` b ON b.name = bs.parent
				WHERE b.show = %(show)s
				  AND bs.seat = %(seat)s
				  AND b.status = 'Reserved'
				  AND b.reservation_expires_at > %(now)s
				LIMIT 1 FOR UPDATE
				""",
				{"show": show, "seat": seat_id, "now": now_datetime()},
			)
			if reserved:
				frappe.db.rollback()
				frappe.throw(
					_("Seat {0} is currently reserved by another user.").format(seat_id)
				)

		# All seats available — create booking
		movie_doc = frappe.get_doc("Movie", show_doc.movie)
		min_price = movie_doc.min_ticket_price or 0
		max_price = movie_doc.max_ticket_price or 0
		
		seat_records = frappe.get_all("Seat", filters={"name": ["in", seats]}, fields=["name", "seat_number", "price"])
		seat_map = {s.name: s for s in seat_records}
		
		seats_list = []
		subtotal = 0.0

		for seat_id in seats:
			seat_doc = seat_map.get(seat_id)
			seat_price = seat_doc.price or 0
			
			if min_price and max_price:
				if seat_price < min_price or seat_price > max_price:
					frappe.throw(
						_("Seat {0} price ({1}) is outside the allowed range ({2} - {3}) for Movie {4}.")
						.format(seat_doc.seat_number, seat_price, min_price, max_price, show_doc.movie)
					)
			
			seats_list.append({
				"seat": seat_id,
				"seat_number": seat_doc.seat_number,
				"price": seat_price,
			})
			subtotal += seat_price

		booking = frappe.get_doc(
			{
				"doctype": "Booking",
				"customer": customer,
				"show": show,
				"status": "Reserved",
				"reservation_expires_at": add_to_date(now_datetime(), minutes=10, as_string=True, as_datetime=True),
				"subtotal": subtotal,
				"discount": 0,
				"tax": 0,
				"grand_total": subtotal,
				"seats": seats_list,
			}
		)
		booking.insert(ignore_permissions=True)
		frappe.db.commit()

		return {
			"booking": booking.name,
			"reservation_expires_at": str(booking.reservation_expires_at),
			"subtotal": subtotal,
		}

	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "reserve_seats error")
		frappe.throw(_("Reservation failed: {0}").format(str(e)))


@frappe.whitelist()
def confirm_booking(
	booking_name: str,
	coupon_code: str = ""
) -> dict:
	"""
	Confirm a Reserved booking.
	- Recalculates pricing server-side based on snapshot seat prices.
	- Validates coupon if provided.
	- Creates ERPNext Sales Invoice.
	- Generates individual Tickets.
	"""
	booking = frappe.get_doc("Booking", booking_name)

	# Permission check: user can only confirm their own booking unless admin
	_check_booking_permission(booking)

	# Status check
	if booking.status != "Reserved":
		frappe.throw(
			_("Only Reserved bookings can be confirmed. Current status: {0}").format(
				booking.status
			)
		)

	# Expiry check (tolerate missing expiry for manually created Desk bookings)
	if booking.reservation_expires_at:
		if get_datetime(booking.reservation_expires_at) < get_datetime(now_datetime()):
			booking.db_set("status", "Expired")
			frappe.throw(_("Reservation has expired. Please start a new booking."))

	show_doc = frappe.get_doc("Show", booking.show)

	# Show validations
	if show_doc.status != "Scheduled":
		frappe.throw(_("Show is no longer available."))
	if getdate(show_doc.show_date) < getdate(nowdate()):
		frappe.throw(_("Cannot confirm a booking for a past show."))

	if not booking.seats:
		frappe.throw(_("No seats in this booking."))

	# Re-validate seats server-side (re-check availability excluding current booking)
	_expire_stale_reservations()
	for seat_row in booking.seats:
		seat_id = seat_row.seat
		# Check confirmed by another booking
		confirmed = frappe.db.sql(
			"""
			SELECT bs.name
			FROM `tabBooking Seat` bs
			INNER JOIN `tabBooking` b ON b.name = bs.parent
			WHERE b.show = %(show)s
			  AND bs.seat = %(seat)s
			  AND b.status = 'Confirmed'
			LIMIT 1
			""",
			{"show": booking.show, "seat": seat_id},
		)
		if confirmed:
			frappe.throw(
				_("Seat {0} has been confirmed by another booking.").format(seat_id)
			)

	# Server-side pricing recalculation (never trust client values)
	subtotal = sum(seat_row.price for seat_row in booking.seats)

	# Coupon discount
	discount = 0.0
	if coupon_code:
		coupon_result = validate_coupon(coupon_code, subtotal)
		discount = coupon_result["discount_amount"]
		booking.coupon = coupon_code

	after_discount = subtotal - discount

	# Tax (using DEFAULT_TAX_RATE; in production fetch from ERPNext tax template)
	tax = after_discount * DEFAULT_TAX_RATE
	grand_total = after_discount + tax

	# Update booking pricing fields
	booking.subtotal = subtotal
	booking.discount = discount
	booking.tax = tax
	booking.grand_total = grand_total
	booking.status = "Confirmed"

	# Create ERPNext Sales Invoice
	invoice_name = _create_sales_invoice(booking, subtotal, discount, tax, grand_total)
	booking.sales_invoice = invoice_name

	booking.save(ignore_permissions=True)

	# Increment coupon usage count
	if coupon_code:
		frappe.db.set_value(
			"Coupon",
			coupon_code,
			"used_count",
			frappe.get_value("Coupon", coupon_code, "used_count") + 1,
		)

	# Generate individual tickets — one per seat
	_generate_tickets(booking)

	frappe.db.commit()

	return {
		"booking": booking.name,
		"status": "Confirmed",
		"grand_total": grand_total,
		"sales_invoice": invoice_name,
	}


@frappe.whitelist()
def cancel_booking(booking_name: str) -> dict:
	"""Cancel a Reserved or Confirmed booking."""
	booking = frappe.get_doc("Booking", booking_name)
	_check_booking_permission(booking)

	if booking.status not in ("Reserved", "Confirmed"):
		frappe.throw(_("Only Reserved or Confirmed bookings can be cancelled."))

	booking.status = "Cancelled"
	booking.save(ignore_permissions=True)

	# Cancel associated tickets
	tickets = frappe.get_all("Ticket", filters={"booking": booking_name}, fields=["name"])
	for t in tickets:
		frappe.db.set_value("Ticket", t.name, "status", "Cancelled")

	frappe.db.commit()
	return {"booking": booking_name, "status": "Cancelled"}


@frappe.whitelist()
def get_today_shows(movie: str = "", theatre: str = "", screen: str = "") -> list:
	"""Return today's scheduled shows with optional filters."""
	filters = {
		"show_date": nowdate(),
		"status": "Scheduled",
	}
	if movie:
		filters["movie"] = movie
	if theatre:
		filters["theatre"] = theatre
	if screen:
		filters["screen"] = screen

	shows = frappe.get_all(
		"Show",
		filters=filters,
		fields=["name", "movie", "theatre", "screen", "show_date",
				"start_time", "end_time", "ticket_price", "status"],
		order_by="start_time asc",
	)
	return shows


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_seats_by_status(show: str, status: str) -> list:
	"""Return seat IDs for a show with a given booking status."""
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT bs.seat
		FROM `tabBooking Seat` bs
		INNER JOIN `tabBooking` b ON b.name = bs.parent
		WHERE b.show = %(show)s AND b.status = %(status)s
		""",
		{"show": show, "status": status},
		as_list=True,
	)
	return [r[0] for r in rows]


def _get_active_reserved_seats(show: str) -> list:
	"""Return seat IDs that are actively reserved (not expired) for a show."""
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT bs.seat
		FROM `tabBooking Seat` bs
		INNER JOIN `tabBooking` b ON b.name = bs.parent
		WHERE b.show = %(show)s
		  AND b.status = 'Reserved'
		  AND b.reservation_expires_at > %(now)s
		""",
		{"show": show, "now": now_datetime()},
		as_list=True,
	)
	return [r[0] for r in rows]


def _expire_stale_reservations():
	"""Mark any expired Reserved bookings as Expired. Called before availability checks."""
	frappe.db.sql(
		"""
		UPDATE `tabBooking`
		SET status = 'Expired', modified = %(now)s
		WHERE status = 'Reserved'
		  AND reservation_expires_at IS NOT NULL
		  AND reservation_expires_at < %(now)s
		""",
		{"now": now_datetime()},
	)


def _check_booking_permission(booking: Document):
	"""Ensure the current user can modify this booking."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	if "Theatre Admin" in roles or "Administrator" in roles:
		return
	# Theatre User can only manage their own bookings
	# Match booking customer to user's linked customer
	customer_name = frappe.db.get_value("Customer", {"email_id": user}, "name")
	if booking.customer != customer_name:
		frappe.throw(_("You do not have permission to modify this booking."), frappe.PermissionError)


def _create_sales_invoice(booking: Document, subtotal: float, discount: float,
						  tax: float, grand_total: float) -> str:
	"""Create an ERPNext Sales Invoice for the confirmed booking."""
	# Ensure 'Movie Ticket' item exists
	_ensure_movie_ticket_item()

	show_doc = frappe.get_doc("Show", booking.show)
	movie_name = frappe.get_value("Movie", show_doc.movie, "movie_name") or show_doc.movie

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": booking.customer,
			"posting_date": nowdate(),
			"due_date": nowdate(),
			"items": [
				{
					"item_code": "Movie Ticket",
					"item_name": "Movie Ticket - {0} (Seat {1})".format(movie_name, seat_row.seat_number),
					"description": "Ticket for {0} on {1} (Seat {2})".format(
						movie_name, show_doc.show_date, seat_row.seat_number
					),
					"qty": 1,
					"rate": seat_row.price,
					"amount": seat_row.price,
				}
				for seat_row in booking.seats
			],
			"discount_amount": discount,
			"apply_discount_on": "Grand Total",
			"taxes": [],
		}
	)

	# Apply tax if any
	if tax and tax > 0:
		invoice.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": _get_tax_account(),
				"description": "Tax",
				"tax_amount": tax,
			},
		)

	invoice.insert(ignore_permissions=True)
	# Submit the invoice so it is posted
	invoice.submit()
	return invoice.name


def _ensure_movie_ticket_item():
	"""Create the 'Movie Ticket' ERPNext item if it doesn't exist."""
	if not frappe.db.exists("Item", "Movie Ticket"):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "Movie Ticket",
				"item_name": "Movie Ticket",
				"item_group": "Services",
				"is_stock_item": 0,
				"description": "Movie Ticket",
			}
		)
		item.insert(ignore_permissions=True)


def _get_tax_account():
	"""Return a default tax account head. Falls back gracefully."""
	# Try to find a standard output tax account
	account = frappe.db.get_value(
		"Account",
		{"account_type": "Tax", "root_type": "Liability", "is_group": 0},
		"name",
	)
	if not account:
		# Use company's default — safe fallback
		company = frappe.defaults.get_global_default("company")
		account = frappe.db.get_value(
			"Account",
			{"company": company, "account_type": "Tax", "root_type": "Liability", "is_group": 0},
			"name",
		)
	return account


def _generate_tickets(booking: Document):
	"""Create one Ticket per seat for a confirmed booking."""
	for seat_row in booking.seats:
		ticket = frappe.get_doc(
			{
				"doctype": "Ticket",
				"naming_series": "TICKET-.YYYY.-.####",
				"booking": booking.name,
				"customer": booking.customer,
				"show": booking.show,
				"seat": seat_row.seat,
				"price": seat_row.price,
				"status": "Active",
			}
		)
		ticket.insert(ignore_permissions=True)
