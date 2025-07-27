import uuid
from django import forms
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone


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
    profile_picture = models.ImageField(upload_to='campushomes/users/', null=True, blank=True)

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
    special_requests = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Booking #{self.id} - {self.booked_property.title if self.booked_property else 'No Property'}"

    def clean(self):
        if not self.booked_property:
            raise ValidationError("A property must be selected for booking.")

        if self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date.")

        # ❗ Skip the past-date validation if status is 'cancelled'
        if self.status != 'cancelled' and self.start_date < timezone.now().date():
            raise ValidationError("Start date cannot be in the past.")

        overlapping = Booking.objects.filter(
            booked_property=self.booked_property,
            status='confirmed',
            start_date__lt=self.end_date,
            end_date__gt=self.start_date
        ).exclude(id=self.id)

        if overlapping.exists():
            raise ValidationError("This property is already booked for the selected dates.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duration(self):
        return (self.end_date - self.start_date).days

    @property
    def total_price(self):
        """
        'hostel', 'house', and 'land' use fixed price;
        others (e.g., room) are multiplied by duration.
        """
        if not self.booked_property or not self.start_date or not self.end_date:
            return 0

        if self.booked_property.property_type in ['hostel', 'house', 'land']:
            return self.booked_property.price

        return self.duration * self.booked_property.price

 



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
    receipt = models.FileField(upload_to='campushomes/payments/', null=True, blank=True)

    def __str__(self):
        return f"Payment #{self.id} - {self.amount}"

    @property
    def receipt_url(self):
        return self.receipt.url if self.receipt else None


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