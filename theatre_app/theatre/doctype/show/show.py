# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_time, nowdate


class Show(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		end_time: DF.Time
		movie: DF.Link
		naming_series: DF.Literal["SHOW-.YYYY.-.####"]
		screen: DF.Link
		show_date: DF.Date
		start_time: DF.Time
		status: DF.Literal["Scheduled", "Cancelled", "Completed"]
		theatre: DF.Link
	# end: auto-generated types

	def validate(self):
		self._validate_show_date()
		self._validate_times()
		self._validate_screen_belongs_to_theatre()
		self._validate_no_overlap()
		self._validate_seat_pricing()

	def _validate_show_date(self):
		"""Show date cannot be in the past."""
		if self.show_date and getdate(self.show_date) < getdate(nowdate()):
			frappe.throw(_("Show date cannot be in the past."))

	def _validate_times(self):
		"""End time must be after start time."""
		if self.start_time and self.end_time:
			if get_time(self.end_time) <= get_time(self.start_time):
				frappe.throw(_("End time must be after start time."))

	def _validate_seat_pricing(self):
		"""Ensure all seats on the selected screen have prices within the movie's allowed range."""
		if not (self.screen and self.movie):
			return
		
		movie_doc = frappe.get_doc("Movie", self.movie)
		min_price = movie_doc.min_ticket_price or 0
		max_price = movie_doc.max_ticket_price or 0

		# Ignore if movie has no bounds configured
		if not min_price and not max_price:
			return

		seats = frappe.get_all("Seat", filters={"screen": self.screen}, fields=["name", "seat_number", "price"])
		for seat in seats:
			seat_price = seat.price or 0
			if seat_price < min_price or seat_price > max_price:
				frappe.throw(
					_("Seat {0} price ({1}) is outside the allowed range ({2} - {3}) for Movie {4}.")
					.format(seat.seat_number, seat_price, min_price, max_price, self.movie)
				)

	def _validate_screen_belongs_to_theatre(self):
		"""The selected screen must belong to the selected theatre."""
		if self.screen and self.theatre:
			screen_theatre = frappe.get_value("Screen", self.screen, "theatre")
			if screen_theatre != self.theatre:
				frappe.throw(
					_("Screen {0} does not belong to Theatre {1}.").format(
						self.screen, self.theatre
					)
				)

	def _validate_no_overlap(self):
		"""Prevent scheduling overlapping shows on the same screen and date."""
		if not (self.screen and self.show_date and self.start_time and self.end_time):
			return

		# Find other shows on same screen/date that are not cancelled
		existing_shows = frappe.get_all(
			"Show",
			filters={
				"screen": self.screen,
				"show_date": self.show_date,
				"status": ["!=", "Cancelled"],
				"name": ["!=", self.name],
			},
			fields=["name", "start_time", "end_time"],
		)

		new_start = get_time(self.start_time)
		new_end = get_time(self.end_time)

		for show in existing_shows:
			existing_start = get_time(show.start_time)
			existing_end = get_time(show.end_time)
			# Overlap condition: new_start < existing_end AND new_end > existing_start
			# Exact boundary touching (end == start of next) is allowed
			if new_start < existing_end and new_end > existing_start:
				frappe.throw(
					_(
						"Show overlaps with existing show {0} ({1} - {2}) on the same screen."
					).format(show.name, show.start_time, show.end_time)
				)

	def on_update(self):
		"""Refresh the parent Theatre's shows child table when a show is updated."""
		if self.theatre:
			theatre_doc = frappe.get_doc("Theatre", self.theatre)
			theatre_doc.refresh_shows()
