from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from bookings.models import Booking, Invoice, Payment, Technician


class DashboardSummaryTests(TestCase):
    def setUp(self):
        self.url = reverse("dashboard_summary")

    def test_anonymous_user_cannot_view_dashboard(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "Administrator login is required.")

    def test_staff_without_dashboard_permissions_cannot_view_dashboard(self):
        user = get_user_model().objects.create_user(
            username="staff-without-permission",
            password="test-password",
            is_staff=True,
        )
        booking_permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="view_booking",
        )
        user.user_permissions.add(booking_permission)
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_authorized_staff_receives_aggregated_private_safe_summary(self):
        user = get_user_model().objects.create_user(
            username="dashboard-admin",
            password="test-password",
            is_staff=True,
        )
        permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="view_booking",
        )
        technician_permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="view_technician",
        )
        invoice_permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="view_invoice",
        )
        payment_permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="view_payment",
        )
        user.user_permissions.add(
            permission,
            technician_permission,
            invoice_permission,
            payment_permission,
        )
        self.client.force_login(user)

        technician = Technician.objects.create(
            full_name="Dashboard Technician",
            phone="9876543210",
            skills="Refrigerator",
            service_area="Central",
        )
        paid_booking = Booking.objects.create(
            customer_name="Private Customer",
            phone="9123456789",
            appliance="Refrigerator",
            service="Repair",
            preferred_date=date(2026, 10, 20),
            address="Private address",
            status="Completed",
            technician=technician,
        )
        pending_booking = Booking.objects.create(
            customer_name="Another Customer",
            phone="9000000000",
            appliance="Air Conditioner",
            service="Maintenance",
            preferred_date=date(2026, 10, 21),
            address="Another private address",
            status="Pending",
        )
        paid_invoice = Invoice.objects.create(booking=paid_booking, labour_charges="1000.00")
        Payment.objects.create(
            invoice=paid_invoice,
            amount="1000.00",
            payment_method="UPI",
            status=Payment.STATUS_PAID,
            transaction_reference="DASH-PAID-001",
        )
        Invoice.objects.create(booking=pending_booking, labour_charges="500.00")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["bookings"]["total"], 2)
        self.assertEqual(data["bookings"]["pending"], 1)
        self.assertEqual(data["bookings"]["completed"], 1)
        self.assertEqual(data["bookings"]["assigned"], 0)
        self.assertEqual(data["technicians"]["total"], 1)
        self.assertEqual(data["technicians"]["available"], 1)
        self.assertEqual(data["payments"]["total_collected"], "1000.00")
        self.assertEqual(data["payments"]["pending_amount"], "500.00")
        self.assertEqual(data["payments"]["paid_invoices"], 1)
        assigned_booking = next(
            booking
            for booking in data["recent_bookings"]
            if booking["assigned_technician"]
        )
        self.assertEqual(assigned_booking["assigned_technician"], technician.full_name)
        for booking in data["recent_bookings"]:
            self.assertNotIn("customer_name", booking)
            self.assertNotIn("phone", booking)
            self.assertNotIn("address", booking)
        self.assertEqual(
            {row["appliance"]: row["count"] for row in data["bookings_by_appliance"]},
            {"Refrigerator": 1, "Air Conditioner": 1},
        )
