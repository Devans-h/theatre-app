// Copyright (c) 2026, Devansh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Booking", {
	refresh(frm) {
		// Show seat availability panel if show is selected
		if (frm.doc.show && frm.doc.status === "Reserved") {
			frm.add_custom_button(__("Refresh Seat Availability"), function () {
				_load_seat_availability(frm);
			});

			frm.add_custom_button(__("Confirm Booking"), function () {
				_confirm_booking(frm);
			}, __("Actions"));
		}

		if (frm.doc.status === "Reserved" || frm.doc.status === "Confirmed") {
			frm.add_custom_button(__("Cancel Booking"), function () {
				frappe.confirm(__("Cancel this booking?"), function () {
					frm.call({
						method:
							"theatre_app.theatre.doctype.booking.booking.cancel_booking",
						args: { booking_name: frm.doc.name },
						callback: function (r) {
							if (!r.exc) {
								frm.reload_doc();
								frappe.msgprint(__("Booking cancelled."));
							}
						},
					});
				});
			}, __("Actions"));
		}

		// Clear existing timer if any
		if (frm.expiry_interval) {
			clearInterval(frm.expiry_interval);
			frm.expiry_interval = null;
			let wrapper = frm.get_field("reservation_expires_at") && frm.get_field("reservation_expires_at").$wrapper;
			if (wrapper) wrapper.find(".expiry-countdown").remove();
		}

		// Show expiry countdown for reserved bookings
		if (frm.doc.status === "Reserved" && frm.doc.reservation_expires_at) {
			_show_expiry_countdown(frm);
		}

		// Display seat availability grid
		if (frm.doc.show && !frm.is_new()) {
			_load_seat_availability(frm);
		}

		// Show billing summary
		_update_billing_display(frm);
	},

	show(frm) {
		if (frm.doc.show) {
			// Load available seats when show is selected
			_load_seat_availability(frm);
			// Clear previously selected seats
			frm.clear_table("seats");
			frm.refresh_field("seats");
			_update_billing_display(frm);
		}
	},

	coupon(frm) {
		// Coupon validation is done server-side; just clear discount display
		_update_billing_display(frm);
	},
});

frappe.ui.form.on("Booking Seat", {
	seat(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (row.seat) {
			frappe.db.get_value("Seat", row.seat, "price", function (r) {
				if (r && r.price !== undefined) {
					frappe.model.set_value(cdt, cdn, "price", r.price);
					_update_billing_display(frm);
				}
			});
		}
	},
});

function _load_seat_availability(frm) {
	if (!frm.doc.show) return;

	frm.call({
		method: "theatre_app.theatre.doctype.booking.booking.get_available_seats",
		args: { show: frm.doc.show },
		callback: function (r) {
			if (r.message) {
				_render_seat_grid(frm, r.message);
			}
		},
	});
}

function _render_seat_grid(frm, seats) {
	// Build an HTML seat map below the form
	let html = `
		<div style="margin: 15px 0;">
			<h5>${__("Seat Availability")}</h5>
			<div style="display: flex; gap: 15px; margin-bottom: 10px; font-size: 12px;">
				<span><span style="background:#28a745;color:#fff;padding:2px 8px;border-radius:3px">■</span> ${__("Available")}</span>
				<span><span style="background:#ffc107;color:#fff;padding:2px 8px;border-radius:3px">■</span> ${__("Reserved")}</span>
				<span><span style="background:#dc3545;color:#fff;padding:2px 8px;border-radius:3px">■</span> ${__("Booked")}</span>
			</div>
			<div style="display: flex; flex-wrap: wrap; gap: 8px; max-width: 600px;">
	`;

	seats.forEach(function (seat) {
		let color =
			seat.status === "Available"
				? "#28a745"
				: seat.status === "Reserved"
				? "#ffc107"
				: "#dc3545";
		let cursor = seat.status === "Available" ? "pointer" : "not-allowed";
		html += `
			<div
				class="seat-btn"
				data-seat="${seat.seat}"
				data-seat-number="${seat.seat_number}"
				data-price="${seat.price}"
				data-status="${seat.status}"
				title="${seat.seat_number} (${seat.seat_type}) - ${format_currency(seat.price)} - ${seat.status}"
				style="
					background:${color};
					color:#fff;
					padding:6px 12px;
					border-radius:4px;
					cursor:${cursor};
					font-size:13px;
					user-select:none;
					text-align:center;
				"
			>
				<div>${seat.seat_number}</div>
				<div style="font-size:10px; opacity:0.8;">${format_currency(seat.price)}</div>
			</div>
		`;
	});

	html += `</div></div>`;

	// Find or create the seat grid wrapper
	if (!frm._seat_grid_wrapper) {
		frm._seat_grid_wrapper = $('<div class="theatre-seat-grid"></div>').appendTo(
			frm.fields_dict.seats.$wrapper
		);
	}
	frm._seat_grid_wrapper.html(html);

	// Attach click handlers
	frm._seat_grid_wrapper.find(".seat-btn[data-status='Available']").on("click", function () {
		let seat = $(this).attr("data-seat");
		let seatNumber = $(this).attr("data-seat-number");
		let price = parseFloat($(this).attr("data-price")) || 0;
		_toggle_seat_selection(frm, seat, seatNumber, price, $(this));
	});

	// Highlight already-selected seats
	let selectedSeats = (frm.doc.seats || []).map((s) => s.seat);
	frm._seat_grid_wrapper.find(".seat-btn").each(function () {
		if (selectedSeats.includes($(this).attr("data-seat"))) {
			$(this).css({ "outline": "3px solid #007bff", "outline-offset": "2px" });
		}
	});
}

function _toggle_seat_selection(frm, seat, seatNumber, price, $btn) {
	let existingRow = (frm.doc.seats || []).find((s) => s.seat === seat);

	if (existingRow) {
		// Deselect
		let idx = frm.doc.seats.indexOf(existingRow);
		frm.doc.seats.splice(idx, 1);
		frm.refresh_field("seats");
		$btn.css({ "outline": "" });
	} else {
		// Select
		let row = frm.add_child("seats");
		row.seat = seat;
		row.seat_number = seatNumber;
		row.price = price;
		frm.refresh_field("seats");
		$btn.css({ "outline": "3px solid #007bff", "outline-offset": "2px" });
	}

	_update_billing_display(frm);
}

function _update_billing_display(frm) {
	// Show subtotal based on sum of selected seat prices
	if (!frm.doc.show) return;

	let numSeats = (frm.doc.seats || []).length;
	let subtotal = (frm.doc.seats || []).reduce((sum, row) => sum + (parseFloat(row.price) || 0), 0);
	
	frm.set_value("subtotal", subtotal);
	frm.set_value("grand_total", subtotal);
	
	if (numSeats > 0) {
		frappe.show_alert(
			__("Subtotal: {0} for {1} seat(s)", [
				format_currency(subtotal),
				numSeats,
			])
		);
	}
}

function _confirm_booking(frm) {
	let couponCode = frm.doc.coupon || "";

	frappe.prompt(
		[
			{
				label: __("Coupon Code (optional)"),
				fieldname: "coupon_code",
				fieldtype: "Data",
				default: couponCode,
			}
		],
		function (values) {
			frm.call({
				method:
					"theatre_app.theatre.doctype.booking.booking.confirm_booking",
				args: {
					booking_name: frm.doc.name,
					coupon_code: values.coupon_code || "",
				},
				callback: function (r) {
					if (!r.exc && r.message) {
						frm.reload_doc();
						frappe.msgprint({
							title: __("Booking Confirmed"),
							message: __(
								"Booking confirmed. Grand Total: {0}. Invoice: {1}",
								[
									format_currency(r.message.grand_total),
									r.message.sales_invoice,
								]
							),
							indicator: "green",
						});
					}
				},
			});
		},
		__("Confirm Booking"),
		__("Confirm")
	);
}

function _show_expiry_countdown(frm) {
	let expiresAt = new Date(frm.doc.reservation_expires_at);
	let wrapper = frm.get_field("reservation_expires_at").$wrapper;

	frm.expiry_interval = setInterval(function () {
		let now = new Date();
		let diff = Math.floor((expiresAt - now) / 1000);
		if (diff <= 0) {
			clearInterval(frm.expiry_interval);
			wrapper.find(".expiry-countdown").text(__("Reservation EXPIRED"));
			frappe.show_alert(
				{ message: __("Your reservation has expired!"), indicator: "red" },
				10
			);
		} else {
			let mins = Math.floor(diff / 60);
			let secs = diff % 60;
			if (!wrapper.find(".expiry-countdown").length) {
				wrapper.append(
					`<span class="expiry-countdown" style="color:red;font-weight:bold;margin-left:10px;"></span>`
				);
			}
			wrapper
				.find(".expiry-countdown")
				.text(`⏱ ${mins}:${String(secs).padStart(2, "0")} remaining`);
		}
	}, 1000);
}

function format_currency(amount) {
	return frappe.format(amount, { fieldtype: "Currency" });
}
