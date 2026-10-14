
from django.contrib import admin
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from .models import Booking, Invoice, Notification, Payment, ServicePricing, Technician


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "sequence",
        "id",
        "customer_name",
        "phone",
        "appliance",
        "status",
        "technician",
        "preferred_date",
    )
    ordering = ("id",)
    list_filter = ("status", "service", "technician")
    search_fields = ("customer_name", "phone", "appliance", "technician__full_name")
    autocomplete_fields = ("technician",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            display_sequence=Window(
                expression=RowNumber(),
                order_by=F("id").asc(),
            )
        )

    @admin.display(description="No.", ordering="display_sequence")
    def sequence(self, obj):
        return obj.display_sequence


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "phone",
        "skills",
        "service_area",
        "availability_status",
        "user",
        "created_at",
    )
    list_filter = ("availability_status",)
    search_fields = ("full_name", "phone", "skills", "service_area", "user__username")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")
    search_fields = ("booking__id", "message")
    readonly_fields = ("booking", "event_key", "notification_type", "message", "created_at")


@admin.register(ServicePricing)
class ServicePricingAdmin(admin.ModelAdmin):
    list_display = ("appliance", "service", "amount", "updated_at")
    list_filter = ("appliance", "service")
    search_fields = ("appliance", "service")


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1
    fields = ("amount", "payment_method", "transaction_reference", "payment_date", "status")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "booking",
        "customer_name",
        "appliance",
        "service",
        "service_date",
        "total_amount",
    )
    list_filter = ("service", "appliance", "service_date")
    search_fields = (
        "invoice_number",
        "booking__id",
        "customer_name",
        "customer_phone",
    )
    autocomplete_fields = ("booking",)
    readonly_fields = (
        "invoice_number",
        "customer_name",
        "customer_phone",
        "service_address",
        "appliance",
        "service",
        "technician_name",
        "service_date",
        "total_amount",
        "created_at",
        "updated_at",
    )
    inlines = (PaymentInline,)

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return self.readonly_fields + ("booking",)
        return self.readonly_fields


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "amount",
        "payment_method",
        "status",
        "payment_date",
    )
    list_filter = ("payment_method", "status", "payment_date")
    search_fields = (
        "invoice__invoice_number",
        "invoice__booking__id",
        "transaction_reference",
    )
    readonly_fields = ("idempotency_key", "created_at")
