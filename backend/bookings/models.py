
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Technician(models.Model):
    AVAILABILITY_CHOICES = [
        ("Available", "Available"),
        ("Unavailable", "Unavailable"),
        ("On Leave", "On Leave"),
    ]

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    skills = models.TextField(help_text="Comma-separated skills or supported appliances")
    service_area = models.CharField(max_length=120)
    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default="Available",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="technician_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Booking(models.Model):
    SERVICE_CHOICES = [
        ("Repair", "Repair"),
        ("Installation", "Installation"),
        ("Maintenance", "Maintenance"),
    ]

    customer_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=10)
    appliance = models.CharField(max_length=100)
    service = models.CharField(
        max_length=20,
        choices=SERVICE_CHOICES,
    )
    preferred_date = models.DateField()
    address = models.TextField()
    issue = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    technician = models.ForeignKey(
        Technician,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bookings",
    )

    def clean(self):
        super().clean()
        if (
            self.technician_id
            and self.technician.availability_status != "Available"
        ):
            raise ValidationError({"technician": "Technician is not available for assignments."})

    def __str__(self):
        return f"{self.customer_name} - {self.appliance}"


class ServicePricing(models.Model):
    APPLIANCE_CHOICES = [
        ("Air Conditioner", "Air Conditioner"),
        ("Refrigerator", "Refrigerator"),
        ("Washing Machine", "Washing Machine"),
        ("Microwave", "Microwave"),
        ("Television", "Television"),
        ("Other Appliances", "Other Appliances"),
    ]

    appliance = models.CharField(max_length=100, choices=APPLIANCE_CHOICES)
    service = models.CharField(max_length=20, choices=Booking.SERVICE_CHOICES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("appliance", "service")
        constraints = [
            models.UniqueConstraint(
                fields=("appliance", "service"),
                name="unique_service_price_per_appliance",
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.appliance} - {self.service}: {self.amount}"


def generate_invoice_number():
    return f"FX-INV-{uuid.uuid4().hex.upper()}"


class Invoice(models.Model):
    booking = models.OneToOneField(
        Booking,
        on_delete=models.PROTECT,
        related_name="invoice",
    )
    invoice_number = models.CharField(
        max_length=40,
        unique=True,
        default=generate_invoice_number,
        editable=False,
    )
    customer_name = models.CharField(max_length=120, blank=True)
    customer_phone = models.CharField(max_length=10, blank=True)
    service_address = models.TextField(blank=True)
    appliance = models.CharField(max_length=100, blank=True)
    service = models.CharField(max_length=20, choices=Booking.SERVICE_CHOICES, blank=True)
    technician_name = models.CharField(max_length=120, blank=True)
    service_date = models.DateField(null=True, blank=True)
    labour_charges = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    spare_parts_charges = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    additional_charges = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def clean(self):
        super().clean()
        if self.booking_id and self._state.adding:
            booking = self.booking
            self.customer_name = booking.customer_name
            self.customer_phone = booking.phone
            self.service_address = booking.address
            self.appliance = booking.appliance
            self.service = booking.service
            self.technician_name = (
                booking.technician.full_name if booking.technician_id else ""
            )
            self.service_date = booking.preferred_date

        charges = (
            self.labour_charges,
            self.spare_parts_charges,
            self.additional_charges,
        )
        subtotal = sum(charges, Decimal("0.00"))
        if self.discount > subtotal:
            raise ValidationError({"discount": "Discount cannot exceed the charges subtotal."})
        self.total_amount = subtotal - self.discount

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def amount_paid(self):
        total = self.payments.filter(
            status__in=Payment.SUCCESSFUL_STATUSES
        ).aggregate(total=Sum("amount"))["total"]
        return total or Decimal("0.00")

    @property
    def balance_due(self):
        return max(self.total_amount - self.amount_paid, Decimal("0.00"))

    @property
    def payment_status(self):
        amount_paid = self.amount_paid
        if self.total_amount > 0 and amount_paid >= self.total_amount:
            return "Paid"
        if amount_paid > 0:
            return "Partially Paid"
        if self.payments.filter(status="Pending").exists():
            return "Pending"
        if self.payments.filter(status="Failed").exists():
            return "Failed"
        return "Pending"

    def __str__(self):
        return self.invoice_number


class Payment(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_PAID = "Paid"
    STATUS_PARTIALLY_PAID = "Partially Paid"
    STATUS_FAILED = "Failed"
    SUCCESSFUL_STATUSES = (STATUS_PAID, STATUS_PARTIALLY_PAID)
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_PARTIALLY_PAID, "Partially Paid"),
        (STATUS_FAILED, "Failed"),
    ]
    METHOD_CHOICES = [
        ("Cash", "Cash"),
        ("UPI", "UPI"),
        ("Card", "Card"),
        ("Bank Transfer", "Bank Transfer"),
    ]

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
    )
    payment_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-payment_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.invoice_id:
            return

        successful_amount = self.invoice.payments.filter(
            status__in=self.SUCCESSFUL_STATUSES
        ).exclude(pk=self.pk).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        outstanding = max(
            self.invoice.total_amount - successful_amount,
            Decimal("0.00"),
        )
        if self.amount > outstanding:
            raise ValidationError({
                "amount": f"Payment cannot exceed the outstanding balance of {outstanding:.2f}."
            })
        if self.status == self.STATUS_PAID and self.amount != outstanding:
            raise ValidationError({
                "status": "A Paid payment must settle the full outstanding balance."
            })
        if self.status == self.STATUS_PARTIALLY_PAID and self.amount >= outstanding:
            raise ValidationError({
                "status": "Use Paid when the payment settles the outstanding balance."
            })

    def save(self, *args, **kwargs):
        if self.transaction_reference:
            self.transaction_reference = self.transaction_reference.strip() or None
        else:
            self.transaction_reference = None
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount} ({self.status})"


class Notification(models.Model):
    TYPE_CHOICES = [
        ("confirmed", "Booking confirmed"),
        ("technician_assigned", "Technician assigned"),
        ("service_started", "Service started"),
        ("service_completed", "Service completed"),
    ]

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_key = models.CharField(max_length=100)
    notification_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("booking", "event_key"),
                name="unique_booking_notification_event",
            ),
        ]

    def __str__(self):
        return f"{self.booking} - {self.get_notification_type_display()}"
