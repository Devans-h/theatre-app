# Copyright (c) 2026, Devansh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class Coupon(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		coupon_code: DF.Data
		discount_type: DF.Literal["Percentage", "Fixed Amount"]
		discount_value: DF.Currency
		enabled: DF.Check
		usage_limit: DF.Int
		used_count: DF.Int
		valid_from: DF.Date | None
		valid_until: DF.Date | None
	# end: auto-generated types

	def validate(self):
		if self.discount_value is not None and self.discount_value <= 0:
			frappe.throw(_("Discount value must be greater than zero."))
		if self.discount_type == "Percentage" and self.discount_value > 100:
			frappe.throw(_("Percentage discount cannot exceed 100%."))
		if self.valid_from and self.valid_until:
			if getdate(self.valid_from) > getdate(self.valid_until):
				frappe.throw(_("Valid From must be before Valid Until."))


def validate_coupon(coupon_code: str, subtotal: float) -> dict:
	"""
	Validate a coupon code and return discount details.
	Called by Booking confirmation logic.
	Returns dict with: discount_amount, coupon_doc
	Raises frappe.ValidationError if invalid.
	"""
	if not coupon_code:
		return {"discount_amount": 0}

	coupon = frappe.db.get_value(
		"Coupon",
		coupon_code,
		["name", "enabled", "discount_type", "discount_value", "valid_from", "valid_until",
		 "usage_limit", "used_count"],
		as_dict=True,
	)

	if not coupon:
		frappe.throw(_("Coupon '{0}' does not exist.").format(coupon_code))

	if not coupon.enabled:
		frappe.throw(_("Coupon '{0}' is not enabled.").format(coupon_code))

	today = getdate(nowdate())
	if coupon.valid_from and getdate(coupon.valid_from) > today:
		frappe.throw(_("Coupon '{0}' is not yet valid.").format(coupon_code))

	if coupon.valid_until and getdate(coupon.valid_until) < today:
		frappe.throw(_("Coupon '{0}' has expired.").format(coupon_code))

	if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
		frappe.throw(_("Coupon '{0}' has reached its usage limit.").format(coupon_code))

	if coupon.discount_type == "Percentage":
		discount_amount = subtotal * (coupon.discount_value / 100)
	else:
		discount_amount = min(coupon.discount_value, subtotal)

	return {"discount_amount": discount_amount, "coupon": coupon}
