# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class TheatreShow(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		end_time: DF.Time | None
		movie: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		show: DF.Link | None
		show_date: DF.Date | None
		start_time: DF.Time | None
		status: DF.Data | None
	# end: auto-generated types

	pass
