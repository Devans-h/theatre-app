# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Seat(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		price: DF.Currency
		row: DF.Data | None
		screen: DF.Link
		seat_number: DF.Data
		seat_type: DF.Literal["Regular", "Premium", "VIP"]
	# end: auto-generated types

	def validate(self):
		self._check_duplicate_seat()
		if self.price is not None and self.price <= 0:
			frappe.throw(_("Seat Price must be greater than zero."))

	def _check_duplicate_seat(self):
		"""Prevent duplicate seat numbers within the same screen."""
		existing = frappe.db.exists(
			"Seat",
			{
				"seat_number": self.seat_number,
				"screen": self.screen,
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("Seat number {0} already exists for Screen {1}.").format(
					self.seat_number, self.screen
				)
			)
