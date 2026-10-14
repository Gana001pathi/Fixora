import decimal

import bookings.models
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0004_technician_user"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServicePricing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("appliance", models.CharField(choices=[("Air Conditioner", "Air Conditioner"), ("Refrigerator", "Refrigerator"), ("Washing Machine", "Washing Machine"), ("Microwave", "Microwave"), ("Television", "Television"), ("Other Appliances", "Other Appliances")], max_length=100)),
                ("service", models.CharField(choices=[("Repair", "Repair"), ("Installation", "Installation"), ("Maintenance", "Maintenance")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("appliance", "service")},
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice_number", models.CharField(default=bookings.models.generate_invoice_number, editable=False, max_length=40, unique=True)),
                ("customer_name", models.CharField(blank=True, max_length=120)),
                ("customer_phone", models.CharField(blank=True, max_length=10)),
                ("service_address", models.TextField(blank=True)),
                ("appliance", models.CharField(blank=True, max_length=100)),
                ("service", models.CharField(blank=True, choices=[("Repair", "Repair"), ("Installation", "Installation"), ("Maintenance", "Maintenance")], max_length=20)),
                ("technician_name", models.CharField(blank=True, max_length=120)),
                ("service_date", models.DateField(blank=True, null=True)),
                ("labour_charges", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("spare_parts_charges", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("additional_charges", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("discount", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("total_amount", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), editable=False, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="invoice", to="bookings.booking")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddConstraint(
            model_name="servicepricing",
            constraint=models.UniqueConstraint(fields=("appliance", "service"), name="unique_service_price_per_appliance"),
        ),
    ]