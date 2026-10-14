import json
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from .models import Booking, Invoice, Notification, Payment, ServicePricing, Technician


class TechnicianApiTests(TestCase):
    def setUp(self):
        self.technician = Technician.objects.create(
            full_name="Alex Technician",
            phone="9876543210",
            skills="Air Conditioner, Refrigerator",
            service_area="Central",
        )
        self.booking = Booking.objects.create(
            customer_name="Booking Customer",
            phone="9123456789",
            appliance="Air Conditioner",
            service="Repair",
            preferred_date=date(2026, 10, 20),
            address="Private customer address",
        )

    def test_booking_list_is_not_public(self):
        response = self.client.get(reverse("bookings_api"))

        self.assertEqual(response.status_code, 401)

    def test_booking_list_is_available_to_authorized_staff(self):
        admin = get_user_model().objects.create_superuser(
            username="booking-list-admin",
            email="booking-list-admin@example.com",
            password="test-password",
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("bookings_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["bookings"]), 1)

    def test_available_technicians_do_not_expose_phone(self):
        Technician.objects.create(
            full_name="Unavailable Technician",
            phone="9000000000",
            skills="Microwave",
            service_area="North",
            availability_status="Unavailable",
        )
        response = self.client.get(reverse("available_technicians"))

        self.assertEqual(response.status_code, 200)
        technicians = response.json()["technicians"]
        self.assertEqual(len(technicians), 1)
        technician = technicians[0]
        self.assertEqual(technician["full_name"], self.technician.full_name)
        self.assertNotIn("phone", technician)
        self.assertNotIn("address", technician)

    def test_tracking_includes_assigned_technician_only_after_phone_match(self):
        self.booking.technician = self.technician
        self.booking.save(update_fields=["technician"])

        response = self.client.get(
            reverse("track_booking"),
            {"booking_id": self.booking.id, "phone": self.booking.phone},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["technician"]["full_name"], self.technician.full_name)
        self.assertNotIn("phone", response.json()["technician"])

        denied = self.client.get(
            reverse("track_booking"),
            {"booking_id": self.booking.id, "phone": "9000000000"},
        )
        self.assertEqual(denied.status_code, 404)

    def test_tracking_returns_null_technician_when_unassigned(self):
        response = self.client.get(
            reverse("track_booking"),
            {"booking_id": self.booking.id, "phone": self.booking.phone},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["technician"])

    def test_booking_technician_endpoint_verifies_phone(self):
        self.booking.technician = self.technician
        self.booking.save(update_fields=["technician"])
        endpoint = reverse("booking_technician", args=[self.booking.id])

        response = self.client.get(endpoint, {"phone": self.booking.phone})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["technician"]["full_name"], self.technician.full_name)
        self.assertNotIn("phone", response.json()["technician"])

        denied = self.client.get(endpoint, {"phone": "9000000000"})
        self.assertEqual(denied.status_code, 404)

    def test_assignment_requires_staff_permissions(self):
        response = self.client.post(
            reverse("assign_technician", args=[self.booking.id]),
            data=json.dumps({"technician_id": self.technician.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.booking.refresh_from_db()
        self.assertIsNone(self.booking.technician)

    def test_staff_can_assign_available_technician(self):
        admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("assign_technician", args=[self.booking.id]),
            data=json.dumps({"technician_id": self.technician.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.technician, self.technician)

    def test_unavailable_technician_cannot_be_assigned(self):
        admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(admin)
        self.technician.availability_status = "On Leave"
        self.technician.save(update_fields=["availability_status"])

        response = self.client.post(
            reverse("assign_technician", args=[self.booking.id]),
            data=json.dumps({"technician_id": self.technician.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.booking.refresh_from_db()
        self.assertIsNone(self.booking.technician)

    def test_assignment_endpoint_enforces_csrf(self):
        admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password",
        )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(admin)

        response = csrf_client.post(
            reverse("assign_technician", args=[self.booking.id]),
            data=json.dumps({"technician_id": self.technician.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)


class TechnicianDashboardApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.technician_user = user_model.objects.create_user(
            username="field-tech",
            password="field-tech-password",
        )
        self.other_user = user_model.objects.create_user(
            username="other-tech",
            password="other-tech-password",
        )
        self.technician = Technician.objects.create(
            full_name="Alex Technician",
            phone="9876543210",
            skills="Air Conditioner",
            service_area="Central",
            user=self.technician_user,
        )
        self.other_technician = Technician.objects.create(
            full_name="Jordan Technician",
            phone="9876543211",
            skills="Refrigerator",
            service_area="North",
            user=self.other_user,
        )
        self.booking = Booking.objects.create(
            customer_name="Assigned Customer",
            phone="9123456789",
            appliance="Air Conditioner",
            service="Repair",
            preferred_date=date(2026, 10, 20),
            address="Assigned service address",
            status="Assigned",
            technician=self.technician,
        )
        self.other_booking = Booking.objects.create(
            customer_name="Private Customer",
            phone="9123456790",
            appliance="Refrigerator",
            service="Maintenance",
            preferred_date=date(2026, 10, 21),
            address="Private service address",
            status="Assigned",
            technician=self.other_technician,
        )

    def test_session_and_job_list_require_a_linked_technician(self):
        anonymous_response = self.client.get(reverse("technician_session"))
        self.assertEqual(anonymous_response.status_code, 401)

        unlinked_staff_user = get_user_model().objects.create_user(
            username="unlinked-admin",
            password="password",
            is_staff=True,
        )
        self.client.force_login(unlinked_staff_user)
        unlinked_response = self.client.get(reverse("technician_session"))
        self.assertEqual(unlinked_response.status_code, 403)

        self.client.force_login(self.technician_user)
        response = self.client.get(reverse("technician_session"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([job["id"] for job in response.json()["jobs"]], [self.booking.id])
        self.assertEqual(response.json()["jobs"][0]["reference"], f"FX-{self.booking.id:06d}")
        self.assertEqual(response.json()["jobs"][0]["address"], self.booking.address)

    def test_technician_login_requires_valid_account_and_links_session(self):
        csrf_client = Client(enforce_csrf_checks=True)
        login_page = csrf_client.get(reverse("technician_session"))
        token = login_page.json()["csrf_token"]

        denied = csrf_client.post(
            reverse("technician_login"),
            data=json.dumps({"username": "field-tech", "password": "wrong"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(denied.status_code, 401)

        response = csrf_client.post(
            reverse("technician_login"),
            data=json.dumps({"username": "field-tech", "password": "field-tech-password"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["technician"]["id"], self.technician.id)
        self.assertEqual(csrf_client.get(reverse("technician_session")).status_code, 200)

    def test_technician_can_advance_only_own_job_and_customer_tracking_updates(self):
        self.client.force_login(self.technician_user)
        endpoint = reverse("update_technician_job_status", args=[self.booking.id])

        started = self.client.post(
            endpoint,
            data=json.dumps({"status": "In Progress"}),
            content_type="application/json",
        )
        self.assertEqual(started.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "In Progress")
        self.assertEqual(self.booking.notifications.filter(event_key="status:in progress").count(), 1)

        tracked = self.client.get(
            reverse("track_booking"),
            {"booking_id": self.booking.id, "phone": self.booking.phone},
        )
        self.assertEqual(tracked.json()["status"], "In Progress")

        completed = self.client.post(
            endpoint,
            data=json.dumps({"status": "Completed"}),
            content_type="application/json",
        )
        self.assertEqual(completed.status_code, 200)
        repeated = self.client.post(
            endpoint,
            data=json.dumps({"status": "Completed"}),
            content_type="application/json",
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(self.booking.notifications.count(), 2)

        other_job = self.client.post(
            reverse("update_technician_job_status", args=[self.other_booking.id]),
            data=json.dumps({"status": "In Progress"}),
            content_type="application/json",
        )
        self.assertEqual(other_job.status_code, 404)
        self.other_booking.refresh_from_db()
        self.assertEqual(self.other_booking.status, "Assigned")

    def test_status_update_requires_csrf_and_valid_transition(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.technician_user)
        endpoint = reverse("update_technician_job_status", args=[self.booking.id])

        denied = csrf_client.post(
            endpoint,
            data=json.dumps({"status": "In Progress"}),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.technician_user)
        invalid = self.client.post(
            endpoint,
            data=json.dumps({"status": "Completed"}),
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 409)

        malformed = self.client.post(
            endpoint,
            data=json.dumps({"status": []}),
            content_type="application/json",
        )
        self.assertEqual(malformed.status_code, 400)


class BookingAdminTests(TestCase):
    def test_booking_ids_are_ascending_with_separate_display_sequence(self):
        bookings = [
            Booking.objects.create(
                customer_name=f"Customer {index}",
                phone="9123456789",
                appliance="Air Conditioner",
                service="Repair",
                preferred_date=date(2026, 10, 20),
                address="Test address",
            )
            for index in range(6)
        ]
        Booking.objects.filter(pk__in=[bookings[0].pk, bookings[2].pk, bookings[3].pk]).delete()

        admin = get_user_model().objects.create_superuser(
            username="booking-admin-sequence",
            email="booking-admin-sequence@example.com",
            password="test-password",
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("admin:bookings_booking_changelist"))

        self.assertEqual(response.status_code, 200)
        rows = list(response.context["cl"].result_list)
        self.assertEqual(
            [(booking.id, booking.display_sequence) for booking in rows],
            [(2, 1), (5, 2), (6, 3)],
        )


class PricingInvoiceApiTests(TestCase):
    def setUp(self):
        self.booking = Booking.objects.create(
            customer_name="Invoice Customer",
            phone="9123456789",
            appliance="Air Conditioner",
            service="Repair",
            preferred_date=date(2026, 10, 20),
            address="Invoice service address",
        )
        self.price = ServicePricing.objects.create(
            appliance=self.booking.appliance,
            service=self.booking.service,
            amount="500.00",
        )
        self.admin = get_user_model().objects.create_superuser(
            username="invoice-admin",
            email="invoice-admin@example.com",
            password="invoice-admin-password",
        )

    def create_invoice(self, payload=None):
        self.client.force_login(self.admin)
        body = {"booking_id": self.booking.id}
        if payload:
            body.update(payload)
        return self.client.post(
            reverse("create_invoice_api"),
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_public_pricing_returns_configured_database_amounts(self):
        response = self.client.get(reverse("service_pricing_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pricing"], [{
            "appliance": "Air Conditioner",
            "service": "Repair",
            "amount": "500.00",
            "updated_at": self.price.updated_at.isoformat(),
        }])

    def test_service_pricing_rejects_negative_amounts(self):
        with self.assertRaises(ValidationError):
            ServicePricing.objects.create(
                appliance="Refrigerator",
                service="Repair",
                amount="-0.01",
            )

    def test_invoice_creation_requires_admin_permission(self):
        payload = json.dumps({"booking_id": self.booking.id})
        anonymous = self.client.post(
            reverse("create_invoice_api"),
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(anonymous.status_code, 401)

        customer = get_user_model().objects.create_user(
            username="invoice-customer",
            password="invoice-customer-password",
        )
        self.client.force_login(customer)
        denied = self.client.post(
            reverse("create_invoice_api"),
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

    def test_invoice_calculates_total_and_rejects_duplicate(self):
        response = self.create_invoice({
            "spare_parts_charges": "200.50",
            "additional_charges": "50.00",
            "discount": "25.50",
        })

        self.assertEqual(response.status_code, 201)
        invoice_data = response.json()["invoice"]
        self.assertEqual(invoice_data["booking_reference"], f"FX-{self.booking.id:06d}")
        self.assertEqual(invoice_data["customer_name"], self.booking.customer_name)
        self.assertEqual(invoice_data["labour_charges"], "500.00")
        self.assertEqual(invoice_data["total_amount"], "725.00")

        duplicate = self.create_invoice()
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(Invoice.objects.filter(booking=self.booking).count(), 1)

    def test_invoice_rejects_negative_amounts_and_excessive_discount(self):
        negative = self.create_invoice({"labour_charges": "-1"})
        self.assertEqual(negative.status_code, 400)
        self.assertIn("labour_charges", negative.json()["error"])

        excessive_discount = self.create_invoice({"discount": "501"})
        self.assertEqual(excessive_discount.status_code, 400)
        self.assertEqual(Invoice.objects.filter(booking=self.booking).count(), 0)

        bad_precision = self.create_invoice({"spare_parts_charges": "1.001"})
        self.assertEqual(bad_precision.status_code, 400)

    def test_invoice_requires_configured_pricing_when_labour_not_supplied(self):
        self.price.delete()
        response = self.create_invoice()

        self.assertEqual(response.status_code, 400)
        self.assertIn("Configure a service price", response.json()["error"])

    def test_customer_invoice_requires_matching_booking_phone(self):
        created = self.create_invoice()
        self.assertEqual(created.status_code, 201)
        endpoint = reverse("customer_invoice_api")

        correct_customer = self.client.get(
            endpoint,
            {"reference": f"FX-{self.booking.id:06d}", "phone": self.booking.phone},
        )
        self.assertEqual(correct_customer.status_code, 200)
        self.assertEqual(
            correct_customer.json()["invoice"]["invoice_number"],
            created.json()["invoice"]["invoice_number"],
        )
        self.assertEqual(correct_customer["Cache-Control"], "no-store")

        wrong_phone = self.client.get(
            endpoint,
            {"reference": f"FX-{self.booking.id:06d}", "phone": "9000000000"},
        )
        self.assertEqual(wrong_phone.status_code, 404)

        other_booking = Booking.objects.create(
            customer_name="Different Customer",
            phone="9000000000",
            appliance="Microwave",
            service="Maintenance",
            preferred_date=date(2026, 10, 21),
            address="Different address",
        )
        another_booking_id = self.client.get(
            endpoint,
            {"reference": f"FX-{other_booking.id:06d}", "phone": other_booking.phone},
        )
        self.assertEqual(another_booking_id.status_code, 404)

        malformed_reference = self.client.get(
            endpoint,
            {"reference": str(self.booking.id), "phone": self.booking.phone},
        )
        self.assertEqual(malformed_reference.status_code, 400)

    def test_tracking_reports_invoice_availability_only_after_phone_match(self):
        self.create_invoice()
        correct_customer = self.client.get(
            reverse("track_booking"),
            {"booking_id": self.booking.id, "phone": self.booking.phone},
        )
        self.assertTrue(correct_customer.json()["invoice_available"])

        wrong_phone = self.client.get(
            reverse("track_booking"),
            {"booking_id": self.booking.id, "phone": "9000000000"},
        )
        self.assertEqual(wrong_phone.status_code, 404)

    def test_invoice_admin_can_view_manage_and_search_invoices(self):
        created = self.create_invoice()
        self.assertEqual(created.status_code, 201)

        changelist = self.client.get(reverse("admin:bookings_invoice_changelist"))
        self.assertEqual(changelist.status_code, 200)
        search = self.client.get(
            reverse("admin:bookings_invoice_changelist"),
            {"q": created.json()["invoice"]["invoice_number"]},
        )
        self.assertEqual(search.status_code, 200)


class PaymentApiTests(TestCase):
    def setUp(self):
        self.booking = Booking.objects.create(
            customer_name="Payment Customer",
            phone="9123456789",
            appliance="Refrigerator",
            service="Repair",
            preferred_date=date(2026, 10, 20),
            address="Payment service address",
        )
        self.invoice = Invoice.objects.create(booking=self.booking, labour_charges="1000.00")
        self.admin = get_user_model().objects.create_superuser(
            username="payment-admin",
            email="payment-admin@example.com",
            password="payment-admin-password",
        )
        self.url = reverse("create_payment_api", args=[self.invoice.id])

    def payment_payload(self, **overrides):
        payload = {
            "idempotency_key": str(uuid.uuid4()),
            "amount": "400.00",
            "payment_method": "UPI",
            "transaction_reference": "PAY-REF-001",
            "payment_date": "2026-10-14T12:30:00Z",
            "status": Payment.STATUS_PARTIALLY_PAID,
        }
        payload.update(overrides)
        return payload

    def post_payment(self, payload):
        self.client.force_login(self.admin)
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_admin_can_record_partial_then_full_payment(self):
        partial = self.post_payment(self.payment_payload())
        self.assertEqual(partial.status_code, 201)
        self.assertEqual(partial.json()["invoice"]["payment_status"], "Partially Paid")
        self.assertEqual(partial.json()["invoice"]["amount_paid"], "400.00")
        self.assertEqual(partial.json()["invoice"]["balance_due"], "600.00")

        paid = self.post_payment(self.payment_payload(
            amount="600.00",
            payment_method="Card",
            transaction_reference="PAY-REF-002",
            status=Payment.STATUS_PAID,
        ))
        self.assertEqual(paid.status_code, 201)
        self.assertEqual(paid.json()["invoice"]["payment_status"], "Paid")
        self.assertEqual(paid.json()["invoice"]["amount_paid"], "1000.00")
        self.assertEqual(paid.json()["invoice"]["balance_due"], "0.00")
        self.assertEqual(self.invoice.payments.count(), 2)

    def test_overpayment_and_inconsistent_payment_status_are_rejected(self):
        partial = self.post_payment(self.payment_payload())
        self.assertEqual(partial.status_code, 201)

        too_much = self.post_payment(self.payment_payload(
            amount="600.01",
            transaction_reference="PAY-OVER-BALANCE",
        ))
        self.assertEqual(too_much.status_code, 400)
        self.assertIn("outstanding balance", str(too_much.json()))

        premature_paid = self.post_payment(self.payment_payload(
            amount="500.00",
            transaction_reference="PAY-INCORRECT-SETTLEMENT",
            status=Payment.STATUS_PAID,
        ))
        self.assertEqual(premature_paid.status_code, 400)
        self.assertEqual(self.invoice.payments.count(), 1)
        self.assertEqual(self.invoice.balance_due, Decimal("600.00"))

    def test_identical_submission_is_idempotent_and_key_reuse_is_rejected(self):
        payload = self.payment_payload()
        created = self.post_payment(payload)
        replay = self.post_payment(payload)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["idempotent_replay"])
        self.assertEqual(created.json()["payment"]["id"], replay.json()["payment"]["id"])
        self.assertEqual(self.invoice.payments.count(), 1)

        reused_key = self.post_payment({**payload, "amount": "350.00"})
        self.assertEqual(reused_key.status_code, 409)
        self.assertEqual(self.invoice.payments.count(), 1)

    def test_pending_and_failed_payments_do_not_reduce_balance(self):
        pending = self.post_payment(self.payment_payload(status=Payment.STATUS_PENDING))
        self.assertEqual(pending.status_code, 201)
        self.assertEqual(pending.json()["invoice"]["amount_paid"], "0.00")
        self.assertEqual(pending.json()["invoice"]["balance_due"], "1000.00")
        self.assertEqual(pending.json()["invoice"]["payment_status"], "Pending")

        failed = self.post_payment(self.payment_payload(
            amount="1000.00",
            transaction_reference="PAY-REF-FAILED",
            status=Payment.STATUS_FAILED,
        ))
        self.assertEqual(failed.status_code, 201)
        self.assertEqual(failed.json()["invoice"]["amount_paid"], "0.00")
        self.assertEqual(failed.json()["invoice"]["balance_due"], "1000.00")

    def test_payment_api_requires_permissions_and_valid_fields(self):
        payload = json.dumps(self.payment_payload())
        anonymous = self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(anonymous.status_code, 401)

        staff = get_user_model().objects.create_user(
            username="payment-viewer",
            password="payment-viewer-password",
            is_staff=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="bookings", codename="view_invoice")
        )
        self.client.force_login(staff)
        denied = self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.admin)
        for invalid_fields in (
            {"amount": "-1"},
            {"payment_method": "Crypto"},
            {"payment_method": []},
            {"status": "Settled"},
            {"status": []},
            {"payment_date": "not-a-date"},
            {"idempotency_key": "invalid"},
        ):
            response = self.client.post(
                self.url,
                data=json.dumps(self.payment_payload(**invalid_fields)),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400, invalid_fields)

        self.assertEqual(self.invoice.payments.count(), 0)

    def test_payment_api_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(
            self.url,
            data=json.dumps(self.payment_payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_invoice_includes_payment_summary_and_history(self):
        payload = self.payment_payload()
        recorded = self.post_payment(payload)
        self.assertEqual(recorded.status_code, 201)

        response = self.client.get(
            reverse("customer_invoice_api"),
            {
                "reference": f"FX-{self.booking.id:06d}",
                "phone": self.booking.phone,
            },
        )

        self.assertEqual(response.status_code, 200)
        invoice = response.json()["invoice"]
        self.assertEqual(invoice["payment_status"], "Partially Paid")
        self.assertEqual(invoice["amount_paid"], "400.00")
        self.assertEqual(invoice["balance_due"], "600.00")
        self.assertEqual(invoice["payments"][0]["payment_method"], "UPI")
        self.assertEqual(invoice["payments"][0]["transaction_reference"], "PAY-REF-001")

    def test_invoice_admin_displays_payment_inline(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("admin:bookings_invoice_change", args=[self.invoice.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_payments-0-amount"')


class BookingNotificationTests(TestCase):
    def setUp(self):
        self.booking = Booking.objects.create(
            customer_name="Notification Customer",
            phone="9123456789",
            appliance="Air Conditioner",
            service="Repair",
            preferred_date=date(2026, 10, 20),
            address="Private address",
        )

    def test_status_notifications_are_created_once_per_event(self):
        for status in ("Confirmed", "In Progress", "Completed"):
            self.booking.status = status
            self.booking.save(update_fields=["status"])
            self.booking.save(update_fields=["status"])

        self.assertEqual(self.booking.notifications.count(), 3)
        self.assertSetEqual(
            set(self.booking.notifications.values_list("notification_type", flat=True)),
            {"confirmed", "service_started", "service_completed"},
        )

    def test_unsaved_status_change_does_not_create_notification(self):
        self.booking.status = "Confirmed"
        self.booking.save(update_fields=["issue"])

        self.assertEqual(self.booking.notifications.count(), 0)
        self.assertEqual(self.booking.status, "Confirmed")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "Pending")

    def test_technician_assignment_notification_is_deduplicated(self):
        technician = Technician.objects.create(
            full_name="Notification Technician",
            phone="9876543210",
            skills="Air Conditioner",
            service_area="Central",
        )

        self.booking.technician = technician
        self.booking.save(update_fields=["technician"])
        self.booking.save(update_fields=["technician"])

        self.assertEqual(self.booking.notifications.count(), 1)
        self.assertEqual(
            self.booking.notifications.get().notification_type,
            "technician_assigned",
        )

    def test_customer_can_list_only_own_notifications_and_mark_read(self):
        notification = Notification.objects.create(
            booking=self.booking,
            event_key="status:confirmed",
            notification_type="confirmed",
            message="Your booking has been confirmed.",
        )
        other_booking = Booking.objects.create(
            customer_name="Other Customer",
            phone="9000000000",
            appliance="Refrigerator",
            service="Repair",
            preferred_date=date(2026, 10, 21),
            address="Other private address",
        )
        other_notification = Notification.objects.create(
            booking=other_booking,
            event_key="status:confirmed",
            notification_type="confirmed",
            message="Another customer's notification.",
        )

        response = self.client.get(
            reverse("customer_notifications"),
            {"booking_id": self.booking.id, "phone": self.booking.phone},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["unread_count"], 1)
        self.assertEqual([item["id"] for item in data["notifications"]], [notification.id])
        self.assertEqual(data["notifications"][0]["type_label"], "Booking confirmed")
        self.assertNotIn("phone", data["notifications"][0])
        self.assertNotIn("customer_name", data["notifications"][0])

        wrong_owner = self.client.post(
            reverse("mark_notification_read", args=[other_notification.id]),
            data=json.dumps({
                "booking_id": self.booking.id,
                "phone": self.booking.phone,
            }),
            content_type="application/json",
        )
        self.assertEqual(wrong_owner.status_code, 404)
        other_notification.refresh_from_db()
        self.assertFalse(other_notification.is_read)

        marked = self.client.post(
            reverse("mark_notification_read", args=[notification.id]),
            data=json.dumps({
                "booking_id": self.booking.id,
                "phone": self.booking.phone,
            }),
            content_type="application/json",
        )
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.json()["notification"]["is_read"])
        self.assertEqual(marked.json()["unread_count"], 0)

    def test_mark_read_requires_csrf(self):
        notification = Notification.objects.create(
            booking=self.booking,
            event_key="status:confirmed",
            notification_type="confirmed",
            message="Your booking has been confirmed.",
        )
        client = Client(enforce_csrf_checks=True)
        listing = client.get(
            reverse("customer_notifications"),
            {"booking_id": self.booking.id, "phone": self.booking.phone},
        )

        response = client.post(
            reverse("mark_notification_read", args=[notification.id]),
            data=json.dumps({
                "booking_id": self.booking.id,
                "phone": self.booking.phone,
            }),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=listing.json()["csrf_token"],
        )

        self.assertEqual(response.status_code, 200)