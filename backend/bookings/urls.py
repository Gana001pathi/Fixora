
from django.urls import path
from .views import (
    assign_technician,
    available_technicians,
    booking_technician,
    bookings_api,
    customer_notifications,
    customer_invoice_api,
    create_invoice_api,
    create_payment_api,
    mark_notification_read,
    service_pricing_api,
    track_booking,
    technician_login,
    technician_logout,
    technician_session,
    update_technician_job_status,
)

urlpatterns = [
    path("", bookings_api, name="bookings_api"),
    path("track/", track_booking, name="track_booking"),
    path("pricing/", service_pricing_api, name="service_pricing_api"),
    path("invoices/", create_invoice_api, name="create_invoice_api"),
    path(
        "invoices/<int:invoice_id>/payments/",
        create_payment_api,
        name="create_payment_api",
    ),
    path("invoices/customer/", customer_invoice_api, name="customer_invoice_api"),
    path("notifications/", customer_notifications, name="customer_notifications"),
    path(
        "notifications/<int:notification_id>/read/",
        mark_notification_read,
        name="mark_notification_read",
    ),
    path("available-technicians/", available_technicians, name="available_technicians"),
    path("technician/session/", technician_session, name="technician_session"),
    path("technician/login/", technician_login, name="technician_login"),
    path("technician/logout/", technician_logout, name="technician_logout"),
    path(
        "technician/jobs/<int:booking_id>/status/",
        update_technician_job_status,
        name="update_technician_job_status",
    ),
    path("<str:booking_id>/technician/", booking_technician, name="booking_technician"),
    path("<str:booking_id>/assign/", assign_technician, name="assign_technician"),
]
