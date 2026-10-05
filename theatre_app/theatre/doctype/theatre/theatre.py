# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Theatre(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from theatre_app.theatre.doctype.theatre_show.theatre_show import TheatreShow

		description: DF.SmallText | None
		location: DF.Data
		rating: DF.Rating
		shows: DF.Table[TheatreShow]
		theatre_name: DF.Data
	# end: auto-generated types

	def on_update(self):
		"""Refresh shows table from linked Show documents."""
		self.refresh_shows()

	def refresh_shows(self):
		"""Sync the shows child table with current shows linked to this theatre."""
		shows = frappe.get_all(
			"Show",
			filters={"theatre": self.name, "status": ["!=", "Cancelled"]},
			fields=["name", "movie", "show_date", "start_time", "end_time", "status"],
			order_by="show_date asc, start_time asc",
		)
		self.set("shows", [])
		for show in shows:
			movie_name = frappe.get_value("Movie", show.movie, "movie_name") if show.movie else ""
			self.append(
				"shows",
				{
					"show": show.name,
					"movie": movie_name,
					"show_date": show.show_date,
					"start_time": show.start_time,
					"end_time": show.end_time,
					"status": show.status,
				},
			)
		self.db_update()
