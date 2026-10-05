# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Screen(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		capacity: DF.Int
		screen_name: DF.Data
		theatre: DF.Link
	# end: auto-generated types

	def validate(self):
		if self.capacity is not None and self.capacity <= 0:
			frappe.throw(_("Screen capacity must be greater than 0."))
