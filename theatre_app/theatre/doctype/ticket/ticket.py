# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class Ticket(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		booking: DF.Link
		customer: DF.Link
		naming_series: DF.Literal["TICKET-.YYYY.-.####"]
		price: DF.Currency
		seat: DF.Link
		show: DF.Link
		status: DF.Literal["Active", "Cancelled"]
	# end: auto-generated types

	pass
