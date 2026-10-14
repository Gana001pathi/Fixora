
import json
import re
import uuid
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Booking, Invoice, Notification, Payment, ServicePricing, Technician


def _positive_integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def _public_technician_details(technician):
    if technician is None:
        return None
    return {
        "id": technician.id,
        "full_name": technician.full_name,
        "skills": technician.skills,
        "service_area": technician.service_area,
        "availability_status": technician.availability_status,
    }


def _notification_data(notification):
    return {
        "id": notification.id,
        "type": notification.notification_type,
        "type_label": notification.get_notification_type_display(),
        "message": notification.message,
        "created_at": notification.created_at.isoformat(),
        "is_read": notification.is_read,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def bookings_api(request):
    if request.method == "GET":
        user = request.user
        if not user.is_authenticated:
            return JsonResponse(
                {"error": "Administrator login is required."},
                status=401,
            )
        if not user.is_staff or not user.has_perm("bookings.view_booking"):
            return JsonResponse(
                {"error": "You are not authorized to view bookings."},
                status=403,
            )

        bookings = Booking.objects.all().order_by("-created_at")

        data = []
        for booking in bookings:
            data.append({
                "id": booking.id,
                "customer_name": booking.customer_name,
                "phone": booking.phone,
                "appliance": booking.appliance,
                "service": booking.service,
                "preferred_date": booking.preferred_date.isoformat(),
                "address": booking.address,
                "issue": booking.issue,
                "status": booking.status,
                "created_at": booking.created_at.isoformat(),
            })

        return JsonResponse({"bookings": data})

    try:
        data = json.loads(request.body)

        booking = Booking.objects.create(
            customer_name=data.get("name", "").strip(),
            phone=data.get("phone", "").strip(),
            appliance=data.get("appliance", "").strip(),
            service=data.get("service", "").strip(),
            preferred_date=data.get("date"),
            address=data.get("address", "").strip(),
            issue=data.get("issue", "").strip(),
        )

        return JsonResponse({
            "message": "Booking created successfully",
            "booking_id": booking.id,
            "reference": f"FX-{booking.id:06d}",
            "status": booking.status,
        }, status=201)

    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid booking data."},
            status=400,
        )


@require_http_methods(["GET"])
def track_booking(request):
    booking_id = request.GET.get("booking_id", "").strip()
    phone = request.GET.get("phone", "").strip()

    if not booking_id.isdigit() or not phone:
        return JsonResponse(
            {"error": "Enter a valid booking reference and mobile number."},
            status=400,
        )

    # References look like FX-000123; the numeric part is the database ID.
    booking = Booking.objects.filter(
        id=int(booking_id),
        phone=phone,
    ).first()

    if booking is None:
        return JsonResponse(
            {"error": "No booking found. Check your reference and mobile number."},
            status=404,
        )

    return JsonResponse({
        "reference": f"FX-{booking.id:06d}",
        "customer_name": booking.customer_name,
        "appliance": booking.appliance,
        "service": booking.service,
        "preferred_date": booking.preferred_date.isoformat(),
        "status": booking.status,
        "created_at": booking.created_at.isoformat(),
        "technician": _public_technician_details(booking.technician),
        "invoice_available": Invoice.objects.filter(booking=booking).exists(),
    })


@require_GET
@ensure_csrf_cookie
def customer_notifications(request):
    booking_id = _positive_integer(request.GET.get("booking_id", ""))
    phone = request.GET.get("phone", "").strip()
    if booking_id is None or not phone:
        return JsonResponse(
            {"error": "Enter a valid booking reference and registered mobile number."},
            status=400,
        )

    booking = Booking.objects.filter(pk=booking_id, phone=phone).first()
    if booking is None:
        return JsonResponse(
            {"error": "No booking found. Check your reference and mobile number."},
            status=404,
        )

    notifications = list(
        Notification.objects.filter(booking=booking).order_by("-created_at", "-id")[:50]
    )
    unread_count = Notification.objects.filter(booking=booking, is_read=False).count()
    return JsonResponse({
        "reference": f"FX-{booking.id:06d}",
        "notifications": [_notification_data(item) for item in notifications],
        "unread_count": unread_count,
        "csrf_token": get_token(request),
    })


@require_POST
def mark_notification_read(request, notification_id):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    booking_id = _positive_integer(data.get("booking_id"))
    phone = data.get("phone")
    if booking_id is None or not isinstance(phone, str) or not phone.strip():
        return JsonResponse(
            {"error": "A valid booking ID and registered mobile number are required."},
            status=400,
        )

    booking = Booking.objects.filter(pk=booking_id, phone=phone.strip()).first()
    if booking is None:
        return JsonResponse(
            {"error": "No booking found. Check your reference and mobile number."},
            status=404,
        )

    notification = Notification.objects.filter(
        pk=notification_id,
        booking=booking,
    ).first()
    if notification is None:
        return JsonResponse({"error": "Notification not found."}, status=404)

    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    unread_count = Notification.objects.filter(booking=booking, is_read=False).count()
    return JsonResponse({
        "notification": _notification_data(notification),
        "unread_count": unread_count,
    })


@require_GET
def available_technicians(request):
    technicians = Technician.objects.filter(
        availability_status="Available"
    ).order_by("full_name")
    return JsonResponse({
        "technicians": [
            _public_technician_details(technician)
            for technician in technicians
        ]
    })


@require_GET
def booking_technician(request, booking_id):
    booking_pk = _positive_integer(booking_id)
    phone = request.GET.get("phone", "").strip()
    if booking_pk is None or not phone:
        return JsonResponse(
            {"error": "Enter a valid booking ID and registered mobile number."},
            status=400,
        )

    booking = Booking.objects.filter(pk=booking_pk, phone=phone).select_related(
        "technician"
    ).first()
    if booking is None:
        return JsonResponse(
            {"error": "No booking found. Check your ID and mobile number."},
            status=404,
        )

    return JsonResponse({
        "reference": f"FX-{booking.id:06d}",
        "technician": _public_technician_details(booking.technician),
    })


@require_POST
def assign_technician(request, booking_id):
    user = request.user
    if (
        not user.is_authenticated
        or not user.is_staff
        or not user.has_perm("bookings.change_booking")
        or not user.has_perm("bookings.view_technician")
    ):
        return JsonResponse(
            {"error": "You are not authorized to assign technicians."},
            status=403,
        )

    booking_pk = _positive_integer(booking_id)
    if booking_pk is None:
        return JsonResponse({"error": "Invalid booking ID."}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    technician_pk = _positive_integer(data.get("technician_id"))
    if technician_pk is None:
        return JsonResponse({"error": "A valid technician_id is required."}, status=400)

    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=booking_pk)
            technician = Technician.objects.select_for_update().get(pk=technician_pk)
            if technician.availability_status != "Available":
                return JsonResponse(
                    {"error": "This technician is not available for assignments."},
                    status=409,
                )

            booking.technician = technician
            try:
                booking.full_clean()
            except ValidationError as error:
                return JsonResponse(
                    {"error": "Invalid technician assignment.", "details": error.message_dict},
                    status=400,
                )
            update_fields = ["technician"]
            if booking.status.strip().casefold() == "pending":
                booking.status = "Assigned"
                update_fields.append("status")
            booking.save(update_fields=update_fields)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found."}, status=404)
    except Technician.DoesNotExist:
        return JsonResponse({"error": "Technician not found."}, status=404)

    return JsonResponse({
        "message": "Technician assigned successfully.",
        "booking_id": booking.id,
        "reference": f"FX-{booking.id:06d}",
        "technician": _public_technician_details(technician),
    })


def _technician_job_data(booking):
    return {
        "id": booking.id,
        "reference": f"FX-{booking.id:06d}",
        "customer_name": booking.customer_name,
        "appliance": booking.appliance,
        "service": booking.service,
        "address": booking.address,
        "preferred_date": booking.preferred_date.isoformat(),
        "status": booking.status,
    }


def _technician_jobs_data(technician):
    bookings = Booking.objects.filter(technician=technician).order_by(
        "preferred_date", "id"
    )
    return [_technician_job_data(booking) for booking in bookings]


def _technician_access(request):
    if not request.user.is_authenticated:
        return None, JsonResponse({"error": "Technician sign-in is required."}, status=401)

    technician = Technician.objects.filter(user=request.user).first()
    if technician is None:
        return None, JsonResponse({"error": "This account is not linked to a technician."}, status=403)
    return technician, None


@ensure_csrf_cookie
@require_GET
def technician_session(request):
    csrf_token = get_token(request)
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Technician sign-in is required.", "csrf_token": csrf_token},
            status=401,
        )

    technician, access_error = _technician_access(request)
    if access_error is not None:
        return JsonResponse(
            {"error": "This account is not linked to a technician.", "csrf_token": csrf_token},
            status=403,
        )

    return JsonResponse({
        "csrf_token": csrf_token,
        "technician": {
            "id": technician.id,
            "full_name": technician.full_name,
        },
        "jobs": _technician_jobs_data(technician),
    })


@require_POST
def technician_login(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return JsonResponse({"error": "Username and password are required."}, status=400)

    user = authenticate(request, username=username.strip(), password=password)
    if user is None:
        return JsonResponse({"error": "Invalid username or password."}, status=401)

    technician = Technician.objects.filter(user=user).first()
    if technician is None:
        return JsonResponse({"error": "This account is not linked to a technician."}, status=403)

    login(request, user)
    return JsonResponse({
        "technician": {"id": technician.id, "full_name": technician.full_name},
        "jobs": _technician_jobs_data(technician),
        "csrf_token": get_token(request),
    })


@require_POST
def technician_logout(request):
    logout(request)
    return JsonResponse({"message": "Signed out."})


@require_POST
def update_technician_job_status(request, booking_id):
    technician, access_error = _technician_access(request)
    if access_error is not None:
        return access_error

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    target_status = data.get("status")
    if not isinstance(target_status, str) or target_status not in {"In Progress", "Completed"}:
        return JsonResponse({"error": "Choose a valid job status."}, status=400)

    with transaction.atomic():
        booking = Booking.objects.select_for_update().filter(
            pk=booking_id,
            technician=technician,
        ).first()
        if booking is None:
            return JsonResponse({"error": "Assigned job not found."}, status=404)

        if booking.status == target_status:
            return JsonResponse({"job": _technician_job_data(booking)})

        current_status = booking.status.strip().casefold()
        allowed_next_statuses = {
            "pending": {"In Progress"},
            "confirmed": {"In Progress"},
            "assigned": {"In Progress"},
            "in progress": {"Completed"},
        }
        if target_status not in allowed_next_statuses.get(current_status, set()):
            return JsonResponse(
                {"error": f"A job with status '{booking.status}' cannot be changed to '{target_status}'."},
                status=409,
            )

        booking.status = target_status
        booking.save(update_fields=["status"])

    return JsonResponse({"job": _technician_job_data(booking)})


@require_GET
def service_pricing_api(request):
    prices = ServicePricing.objects.all()
    return JsonResponse({
        "pricing": [
            {
                "appliance": price.appliance,
                "service": price.service,
                "amount": str(price.amount),
                "updated_at": price.updated_at.isoformat(),
            }
            for price in prices
        ]
    })


def _invoice_data(invoice):
    payments = list(invoice.payments.all())
    return {
        "invoice_number": invoice.invoice_number,
        "booking_reference": f"FX-{invoice.booking_id:06d}",
        "customer_name": invoice.customer_name,
        "customer_phone": invoice.customer_phone,
        "service_address": invoice.service_address,
        "appliance": invoice.appliance,
        "service": invoice.service,
        "technician": invoice.technician_name or None,
        "service_date": invoice.service_date.isoformat() if invoice.service_date else None,
        "labour_charges": str(invoice.labour_charges),
        "spare_parts_charges": str(invoice.spare_parts_charges),
        "additional_charges": str(invoice.additional_charges),
        "discount": str(invoice.discount),
        "total_amount": str(invoice.total_amount),
        "payment_status": invoice.payment_status,
        "amount_paid": f"{invoice.amount_paid:.2f}",
        "balance_due": f"{invoice.balance_due:.2f}",
        "payments": [_payment_data(payment) for payment in payments],
        "created_at": invoice.created_at.isoformat(),
    }


def _payment_data(payment):
    return {
        "id": payment.id,
        "amount": str(payment.amount),
        "payment_method": payment.payment_method,
        "transaction_reference": payment.transaction_reference,
        "payment_date": payment.payment_date.isoformat(),
        "status": payment.status,
    }


def _invoice_admin_error(request, permission):
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({"error": "Administrator login is required."}, status=401)
    if not user.is_staff or not user.has_perm(permission):
        return JsonResponse({"error": "You are not authorized to manage invoices."}, status=403)
    return None


def _nonnegative_amount(data, field_name, default):
    value = data.get(field_name, default)
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{field_name} must be a non-negative amount.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field_name} must be a valid amount.") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{field_name} must be a non-negative amount.")
    return amount


def _payment_request_matches(payment, invoice_id, amount, payment_method, transaction_reference, payment_date, status):
    return (
        payment.invoice_id == invoice_id
        and payment.amount == amount
        and payment.payment_method == payment_method
        and payment.transaction_reference == transaction_reference
        and payment.payment_date == payment_date
        and payment.status == status
    )


def _payment_response(payment, status=201, replayed=False):
    return JsonResponse({
        "payment": _payment_data(payment),
        "invoice": {
            "payment_status": payment.invoice.payment_status,
            "amount_paid": f"{payment.invoice.amount_paid:.2f}",
            "balance_due": f"{payment.invoice.balance_due:.2f}",
        },
        "idempotent_replay": replayed,
    }, status=status)


@require_POST
def create_payment_api(request, invoice_id):
    access_error = _invoice_admin_error(request, "bookings.add_payment")
    if access_error is not None:
        return access_error
    if not request.user.has_perm("bookings.view_invoice"):
        return JsonResponse({"error": "You are not authorized to view invoices."}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    try:
        idempotency_key = uuid.UUID(data.get("idempotency_key", ""))
    except (AttributeError, TypeError, ValueError):
        return JsonResponse({"error": "A valid idempotency_key UUID is required."}, status=400)

    try:
        amount = _nonnegative_amount(data, "amount", None)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    if amount <= 0:
        return JsonResponse({"error": "amount must be greater than zero."}, status=400)

    payment_method = data.get("payment_method")
    if not isinstance(payment_method, str) or payment_method not in dict(Payment.METHOD_CHOICES):
        return JsonResponse({"error": "Choose Cash, UPI, Card, or Bank Transfer."}, status=400)

    status = data.get("status")
    if not isinstance(status, str) or status not in dict(Payment.STATUS_CHOICES):
        return JsonResponse({"error": "Choose a valid payment status."}, status=400)

    raw_payment_date = data.get("payment_date")
    if not isinstance(raw_payment_date, str):
        return JsonResponse({"error": "payment_date must be an ISO date or datetime."}, status=400)
    payment_date = parse_datetime(raw_payment_date)
    if payment_date is None:
        parsed_date = parse_date(raw_payment_date)
        if parsed_date is None:
            return JsonResponse({"error": "payment_date must be an ISO date or datetime."}, status=400)
        payment_date = datetime.combine(parsed_date, time.min)
    if timezone.is_naive(payment_date):
        payment_date = timezone.make_aware(payment_date)

    transaction_reference = data.get("transaction_reference", "")
    if transaction_reference is None:
        transaction_reference = ""
    if not isinstance(transaction_reference, str):
        return JsonResponse({"error": "transaction_reference must be text."}, status=400)
    transaction_reference = transaction_reference.strip() or None
    if transaction_reference and len(transaction_reference) > 100:
        return JsonResponse({"error": "transaction_reference cannot exceed 100 characters."}, status=400)

    try:
        with transaction.atomic():
            replay = Payment.objects.filter(idempotency_key=idempotency_key).select_related(
                "invoice"
            ).first()
            if replay is not None:
                if _payment_request_matches(
                    replay,
                    invoice_id,
                    amount,
                    payment_method,
                    transaction_reference,
                    payment_date,
                    status,
                ):
                    return _payment_response(replay, status=200, replayed=True)
                return JsonResponse(
                    {"error": "This idempotency_key was already used for a different payment."},
                    status=409,
                )

            invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
            payment = Payment(
                invoice=invoice,
                amount=amount,
                payment_method=payment_method,
                transaction_reference=transaction_reference,
                payment_date=payment_date,
                status=status,
                idempotency_key=idempotency_key,
            )
            payment.save()
    except Invoice.DoesNotExist:
        return JsonResponse({"error": "Invoice not found."}, status=404)
    except ValidationError as error:
        details = error.message_dict if hasattr(error, "message_dict") else error.messages
        return JsonResponse({"error": "Payment is invalid.", "details": details}, status=400)
    except IntegrityError:
        replay = Payment.objects.filter(idempotency_key=idempotency_key).select_related(
            "invoice"
        ).first()
        if replay is not None and _payment_request_matches(
            replay,
            invoice_id,
            amount,
            payment_method,
            transaction_reference,
            payment_date,
            status,
        ):
            return _payment_response(replay, status=200, replayed=True)
        return JsonResponse(
            {"error": "Duplicate payment or transaction reference."},
            status=409,
        )

    return _payment_response(payment)


@require_POST
def create_invoice_api(request):
    access_error = _invoice_admin_error(request, "bookings.add_invoice")
    if access_error is not None:
        return access_error

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    booking_id = _positive_integer(data.get("booking_id"))
    if booking_id is None:
        return JsonResponse({"error": "A valid booking_id is required."}, status=400)

    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().select_related(
                "technician"
            ).get(pk=booking_id)
            if Invoice.objects.filter(booking=booking).exists():
                return JsonResponse(
                    {"error": "An invoice already exists for this booking."},
                    status=409,
                )

            price = ServicePricing.objects.filter(
                appliance=booking.appliance,
                service=booking.service,
            ).first()
            if price is None and "labour_charges" not in data:
                return JsonResponse(
                    {"error": "Configure a service price or provide labour_charges before creating the invoice."},
                    status=400,
                )

            default_labour = price.amount if price is not None else Decimal("0.00")
            invoice = Invoice(
                booking=booking,
                labour_charges=_nonnegative_amount(data, "labour_charges", default_labour),
                spare_parts_charges=_nonnegative_amount(
                    data, "spare_parts_charges", Decimal("0.00")
                ),
                additional_charges=_nonnegative_amount(
                    data, "additional_charges", Decimal("0.00")
                ),
                discount=_nonnegative_amount(data, "discount", Decimal("0.00")),
            )
            invoice.full_clean()
            invoice.save()
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found."}, status=404)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except ValidationError as error:
        details = error.message_dict if hasattr(error, "message_dict") else error.messages
        return JsonResponse({"error": "Invoice data is invalid.", "details": details}, status=400)
    except IntegrityError:
        return JsonResponse(
            {"error": "An invoice already exists for this booking."},
            status=409,
        )

    return JsonResponse({"invoice": _invoice_data(invoice)}, status=201)


@require_GET
def customer_invoice_api(request):
    reference = request.GET.get("reference", "").strip().upper()
    phone = request.GET.get("phone", "").strip()
    match = re.fullmatch(r"FX-(\d+)", reference)
    if match is None or not phone:
        return JsonResponse(
            {"error": "Enter a valid booking reference and registered mobile number."},
            status=400,
        )

    booking = Booking.objects.filter(pk=int(match.group(1)), phone=phone).first()
    if booking is None:
        return JsonResponse(
            {"error": "No booking found. Check your reference and mobile number."},
            status=404,
        )

    invoice = Invoice.objects.filter(booking=booking).first()
    if invoice is None:
        return JsonResponse({"error": "An invoice is not available for this booking yet."}, status=404)

    response = JsonResponse({"invoice": _invoice_data(invoice)})
    response["Cache-Control"] = "no-store"
    return response
