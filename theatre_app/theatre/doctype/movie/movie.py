# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class Movie(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		duration: DF.Duration | None
		movie_name: DF.Data
		rating: DF.Rating
		min_ticket_price: DF.Currency
		max_ticket_price: DF.Currency
	# end: auto-generated types

	def validate(self):
		if self.min_ticket_price is not None and self.min_ticket_price <= 0:
			frappe.throw(_("Minimum Ticket Price must be greater than zero."))
		if self.max_ticket_price is not None and self.max_ticket_price <= 0:
			frappe.throw(_("Maximum Ticket Price must be greater than zero."))
		if self.min_ticket_price is not None and self.max_ticket_price is not None:
			if self.min_ticket_price > self.max_ticket_price:
				frappe.throw(_("Minimum Ticket Price cannot be greater than Maximum Ticket Price."))

