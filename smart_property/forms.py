from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from datetime import date
from .models import Property, Booking, Amenity, PropertyImage
from django.utils.safestring import mark_safe
User = get_user_model()

# --------------------------
# Custom Widgets and Fields
# --------------------------

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)

class AmenityModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return mark_safe(f'<i class="fas fa-{obj.icon}"></i> {obj.name}')
# --------------------------
# User Registration Form
# --------------------------

class CustomUserCreationForm(UserCreationForm):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('owner', 'Property Owner'),
        ('user', 'User'),
        
    )
    
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)
    phone_number = forms.CharField(max_length=15, required=False)
    profile_picture = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'phone_number', 'profile_picture', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email


# --------------------------
# Property Form
# --------------------------

class PropertyForm(forms.ModelForm):
    images = MultipleFileField(required=False)
    amenities = AmenityModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Property
        fields = [
            'title', 'description', 'price', 'property_type',
            'location', 'address', 'amenities', 'is_available'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['amenities'].initial = self.instance.amenities.all()


# --------------------------
# Booking Form
# --------------------------

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['start_date', 'end_date', 'special_requests']
        widgets = {
            'start_date': forms.DateInput(
                attrs={
                    'type': 'date', 
                    'class': 'form-control datepicker',
                    'min': date.today().isoformat()
                }
            ),
            'end_date': forms.DateInput(
                attrs={
                    'type': 'date', 
                    'class': 'form-control datepicker',
                    'min': date.today().isoformat()
                }
            ),
            'special_requests': forms.Textarea(
                attrs={
                    'rows': 3, 
                    'class': 'form-control',
                    'placeholder': 'Any special requirements...'
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date < date.today():
                raise ValidationError("Start date cannot be in the past.")
            if end_date <= start_date:
                raise ValidationError("End date must be after start date.")
        
        return cleaned_data


# --------------------------
# Amenity Form
# --------------------------

class AmenityForm(forms.ModelForm):
    class Meta:
        model = Amenity
        fields = ['name', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Font Awesome icon name (e.g., "wifi", "swimming-pool")'
            }),
        }


# --------------------------
# Property Image Form
# --------------------------

class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ['image', 'is_primary']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PaymentForm(forms.Form):
    amount = forms.DecimalField(min_value=0)
    payment_method = forms.ChoiceField(choices=[ ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money')])
