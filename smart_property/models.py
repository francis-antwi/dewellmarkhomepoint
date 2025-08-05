import uuid
from django import forms
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings


# Custom widget for multiple file uploads
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('owner', 'Property Owner'),
        ('admin', 'Administrator'),
        ('user', 'User'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    phone_number = models.CharField(max_length=15, blank=True)
    profile_picture = models.ImageField(upload_to='dwellmark/users/', null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def profile_picture_url(self):
        return self.profile_picture.url if self.profile_picture else None


class Amenity(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Amenities"


class Property(models.Model):
    PROPERTY_TYPE_CHOICES = (
        ('hostel', 'Hostel'),
        ('room', 'Room'),
        ('house', 'House'),
        ('land', 'Land'),
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='properties')
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPE_CHOICES)
    bedrooms = models.PositiveIntegerField(default=1)
    location = models.CharField(max_length=200)
    address = models.TextField()
    amenities = models.ManyToManyField(Amenity, blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.location}"

    @property
    def average_rating(self):
        """Calculate average rating for the property"""
        reviews = self.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews) / len(reviews)
        return 0

    @property
    def review_count(self):
        """Get total number of reviews"""
        return self.reviews.count()

    @property
    def primary_image(self):
        """Get primary image or first image"""
        primary = self.images.filter(is_primary=True).first()
        if primary:
            return primary
        return self.images.first()

    def has_confirmed_bookings_for_dates(self, start_date, end_date):
        """Check if property has confirmed bookings for given date range"""
        return self.bookings.filter(
            status='confirmed',
            start_date__lt=end_date,
            end_date__gt=start_date
        ).exists()

    class Meta:
        verbose_name_plural = "Properties"
        ordering = ['-created_at']


class PropertyForm(forms.ModelForm):
    images = MultipleFileField(required=False)
    
    class Meta:
        model = Property
        fields = [
            'title', 'description', 'price', 'property_type',
            'location', 'address', 'amenities', 'is_available'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'amenities': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Customize the amenities queryset if needed
        self.fields['amenities'].queryset = Amenity.objects.all()
        
        # Set initial amenities if editing existing property
        if self.instance and self.instance.pk:
            self.fields['amenities'].initial = self.instance.amenities.all()
        
        # Add Bootstrap classes to form fields
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxSelectMultiple, MultipleFileInput)):
                field.widget.attrs.update({'class': 'form-control'})


class PropertyImage(models.Model):
    property_ref = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='property_images/')
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.property_ref.title}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Unset previous primary image for the same property
            PropertyImage.objects.filter(property_ref=self.property_ref, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

    @property
    def image_url(self):
        return self.image.url if self.image else None


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    )

    booked_property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bookings')
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Track when status changes
    special_requests = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True, null=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)  # Track confirmation time

    def __str__(self):
        return f"Booking #{self.id} - {self.booked_property.title if self.booked_property else 'No Property'}"

    def clean(self):
        if not self.booked_property:
            raise ValidationError("A property must be selected for booking.")

        if self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date.")

        # Skip the past-date validation if status is 'cancelled'
        if self.status != 'cancelled' and self.start_date < timezone.now().date():
            raise ValidationError("Start date cannot be in the past.")

        # Check for overlapping confirmed bookings
        overlapping = Booking.objects.filter(
            booked_property=self.booked_property,
            status='confirmed',
            start_date__lt=self.end_date,
            end_date__gt=self.start_date
        ).exclude(id=self.id)

        if overlapping.exists():
            raise ValidationError("This property is already booked for the selected dates.")

    def save(self, *args, **kwargs):
        # Set confirmed_at timestamp when status changes to confirmed
        if self.status == 'confirmed' and not self.confirmed_at:
            self.confirmed_at = timezone.now()
        
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duration(self):
        return (self.end_date - self.start_date).days

    @property
    def total_price(self):
        """
        Calculate total price based on property type:
        - 'hostel', 'house', 'land' use fixed price
        - 'room' is multiplied by duration
        """
        if not self.booked_property or not self.start_date or not self.end_date:
            return 0

        if self.booked_property.property_type in ['hostel', 'house', 'land']:
            return self.booked_property.price

        return self.duration * self.booked_property.price

    @property
    def is_past_due(self):
        """Check if booking end date has passed"""
        return self.end_date < timezone.now().date()

    @property
    def can_be_cancelled(self):
        """Check if booking can still be cancelled"""
        return self.status in ['pending', 'confirmed'] and not self.is_past_due

    def confirm_booking(self):
        """Method to confirm booking (useful for programmatic confirmation)"""
        if self.status == 'pending':
            self.status = 'confirmed'
            self.confirmed_at = timezone.now()
            self.save(update_fields=['status', 'confirmed_at', 'updated_at'])
            return True
        return False

    def cancel_booking(self, reason=""):
        """Method to cancel booking"""
        if self.can_be_cancelled:
            self.status = 'cancelled'
            self.cancel_reason = reason
            self.save(update_fields=['status', 'cancel_reason', 'updated_at'])
            return True
        return False


class Payment(models.Model):
    PAYMENT_METHODS = (
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
    )

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, unique=True)
    is_successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)  # Track verification time
    receipt = models.FileField(upload_to='dwellmark/payments/', null=True, blank=True)

    def __str__(self):
        return f"Payment #{self.id} - {self.amount} ({self.get_payment_method_display()})"

    @property
    def receipt_url(self):
        return self.receipt.url if self.receipt else None

    def verify_payment(self):
        """Method to verify payment and auto-confirm booking"""
        if not self.is_successful:
            self.is_successful = True
            self.verified_at = timezone.now()
            self.save(update_fields=['is_successful', 'verified_at'])
            
            # Auto-confirm the booking
            self.booking.confirm_booking()
            return True
        return False


class Review(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.user.username} for {self.property.title}"

    class Meta:
        unique_together = ('property', 'user')


# ============================
# 🔹 DJANGO SIGNALS FOR AUTOMATIC ACTIONS
# ============================

@receiver(post_save, sender=Payment)
def auto_confirm_booking_on_payment(sender, instance, created, **kwargs):
    """
    Automatically confirm booking when payment is successful
    """
    if instance.is_successful and instance.booking.status == 'pending':
        instance.booking.confirm_booking()


@receiver(post_save, sender=Booking)
def send_booking_notification(sender, instance, created, **kwargs):
    """
    Send email notifications for booking status changes
    """
    try:
        if created:
            # New booking created - notify property owner
            subject = f"New Booking Request - {instance.booked_property.title}"
            message = f"""
            You have received a new booking request:
            
            Property: {instance.booked_property.title}
            Tenant: {instance.tenant.get_full_name() or instance.tenant.username}
            Dates: {instance.start_date} to {instance.end_date}
            Total: ${instance.total_price}
            
            Please review and confirm the booking.
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [instance.booked_property.owner.email],
                fail_silently=True
            )
            
        elif instance.status == 'confirmed' and instance.confirmed_at:
            # Booking confirmed - notify tenant
            subject = f"Booking Confirmed - {instance.booked_property.title}"
            message = f"""
            Great news! Your booking has been confirmed:
            
            Property: {instance.booked_property.title}
            Dates: {instance.start_date} to {instance.end_date}
            Total Paid: ${instance.total_price}
            
            Thank you for choosing our platform!
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [instance.tenant.email],
                fail_silently=True
            )
            
    except Exception as e:
        # Log error but don't break the booking process
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send booking notification: {e}")


# ============================
# 🔹 ADDITIONAL FORMS
# ============================

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['start_date', 'end_date', 'special_requests']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'special_requests': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Any special requests or notes...'})
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if end_date <= start_date:
                raise forms.ValidationError("End date must be after start date.")
            
            if start_date < timezone.now().date():
                raise forms.ValidationError("Start date cannot be in the past.")

        return cleaned_data


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_method', 'receipt']
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'receipt': forms.FileInput(attrs={'class': 'form-control'})
        }

    amount = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'readonly': True}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['receipt'].help_text = "Upload payment receipt (optional for credit card payments)"