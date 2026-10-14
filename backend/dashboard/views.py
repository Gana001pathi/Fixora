from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from bookings.models import Booking, Invoice, Payment, Technician


def _dashboard_access_error(user):
    if not user.is_authenticated:
        return JsonResponse({"error": "Administrator login is required."}, status=401)
    dashboard_permissions = (
        "bookings.view_booking",
        "bookings.view_technician",
        "bookings.view_invoice",
        "bookings.view_payment",
    )
    if not user.is_staff or not all(user.has_perm(permission) for permission in dashboard_permissions):
        return JsonResponse({"error": "You are not authorized to view the dashboard."}, status=403)
    return None


@require_GET
def dashboard_summary(request):
    access_error = _dashboard_access_error(request.user)
    if access_error is not None:
        return access_error

    booking_totals = Booking.objects.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status__iexact="Pending")),
        confirmed=Count("id", filter=Q(status__iexact="Confirmed")),
        assigned=Count("id", filter=Q(status__iexact="Assigned")),
        in_progress=Count("id", filter=Q(status__iexact="In Progress")),
        completed=Count("id", filter=Q(status__iexact="Completed")),
    )
    technician_totals = Technician.objects.aggregate(
        total=Count("id"),
        available=Count("id", filter=Q(availability_status="Available")),
        unavailable=Count("id", filter=~Q(availability_status="Available")),
    )
    total_collected = Payment.objects.filter(
        status__in=Payment.SUCCESSFUL_STATUSES
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    total_invoiced = Invoice.objects.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    invoice_totals = dict(Invoice.objects.filter(total_amount__gt=0).values_list("id", "total_amount"))
    payments_by_invoice = Payment.objects.filter(
        status__in=Payment.SUCCESSFUL_STATUSES
    ).values("invoice_id").annotate(total_paid=Sum("amount"))
    paid_invoice_count = sum(
        1
        for row in payments_by_invoice
        if row["invoice_id"] in invoice_totals
        and row["total_paid"] >= invoice_totals[row["invoice_id"]]
    )

    recent_bookings = Booking.objects.select_related("technician").order_by(
        "-created_at", "-id"
    )[:10]

    return JsonResponse({
        "bookings": booking_totals,
        "technicians": technician_totals,
        "payments": {
            "total_collected": f"{total_collected:.2f}",
            "pending_amount": f"{max(total_invoiced - total_collected, Decimal('0.00')):.2f}",
            "paid_invoices": paid_invoice_count,
        },
        "recent_bookings": [
            {
                "id": booking.id,
                "reference": f"FX-{booking.id:06d}",
                "appliance": booking.appliance,
                "service": booking.service,
                "status": booking.status,
                "preferred_date": booking.preferred_date.isoformat(),
                "assigned_technician": (
                    booking.technician.full_name if booking.technician_id else None
                ),
            }
            for booking in recent_bookings
        ],
        "bookings_by_status": list(
            Booking.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        ),
        "bookings_by_appliance": list(
            Booking.objects.values("appliance")
            .annotate(count=Count("id"))
            .order_by("-count", "appliance")
        ),
    })
