from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib import messages
from django.db import models
from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .models import Property, Booking, Payment, Review, Amenity, PropertyImage
from .serializers import (
    UserSerializer, PropertySerializer, BookingSerializer, 
    PaymentSerializer, ReviewSerializer, AmenitySerializer,
    PropertyImageSerializer
)
from .utils import initialize_paystack_transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import requests
from django.conf import settings
from .forms import CustomUserCreationForm, PropertyForm, BookingForm
from .permissions import IsOwnerOrReadOnly, IsBookingParticipant
from datetime import datetime
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST
from .forms import PaymentForm 
import uuid
User = get_user_model()
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from .models import Payment
from django.conf import settings
import json
import hmac
import hashlib
import logging
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, Min, Max
from .models import Property


# ============================
# 🔹 API VIEWSETS
# ============================

# 🔹 API VIEWSETS

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        if self.action in ['create']:
            return [permissions.AllowAny()]
        elif self.action in ['destroy', 'update', 'partial_update']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=user.id)


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.all()
    serializer_class = PropertySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['property_type', 'price', 'is_available']
    search_fields = ['title', 'location', 'description']
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        elif self.action in ['create']:
            return [permissions.IsAuthenticated()]
        return [IsOwnerOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated, IsBookingParticipant]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['property', 'status']
    ordering_fields = ['start_date', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Booking.objects.all()
        return Booking.objects.filter(models.Q(tenant=user) | models.Q(property__owner=user))

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsBookingParticipant]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Payment.objects.all()
        return Payment.objects.filter(
            models.Q(booking__tenant=user) | 
            models.Q(booking__property__owner=user)
        )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        payment = self.get_object()
        payment.is_successful = True
        payment.save()
        return Response({'status': 'payment verified'})


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AmenityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer
    permission_classes = [permissions.AllowAny]


class PropertyImageViewSet(viewsets.ModelViewSet):
    queryset = PropertyImage.objects.all()
    serializer_class = PropertyImageSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

# ============================
# 🔹 TEMPLATE VIEWS
# ============================

def index_view(request):
    properties = Property.objects.filter(is_available=True).order_by('-created_at')[:8]
    featured = Property.objects.filter(is_available=True).order_by('?')[:3]
    return render(request, 'index.html', {'properties': properties, 'featured': featured})


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})


@login_required
def dashboard_view(request):
    user = request.user
    context = {}

    # Fetch reviews made by this user
    user_reviews = Review.objects.filter(user=user).order_by('-created_at')

    if user.role == 'owner':
        properties = Property.objects.filter(owner=user).prefetch_related('bookings')
        bookings = Booking.objects.filter(booked_property__owner=user).order_by('-created_at')[:5]


        context.update({
            'properties': properties,
            'bookings': bookings,
        })
    else:
        bookings = Booking.objects.filter(tenant=user).order_by('-created_at')[:5]
        context['bookings'] = bookings

    # Stats
    context['reviews_count'] = user_reviews.count()

    # Optional: recent activity list
    recent_activity = []
    for review in user_reviews[:5]:
        recent_activity.append({
            'icon': 'star',
            'message': f'Reviewed "{review.property.title}"',
            'time': review.created_at
        })

    context['recent_activity'] = recent_activity

    return render(request, 'dashboard.html', context)
@login_required
def property_detail_view(request, pk):
    property = get_object_or_404(Property, pk=pk)
    is_owner = property.owner == request.user
    bookings = property.bookings.filter(status='confirmed')
    booked_dates = [{'from': b.start_date.strftime('%Y-%m-%d'), 'to': b.end_date.strftime('%Y-%m-%d')} for b in bookings]
    
    form = BookingForm(request.POST or None)

    if request.method == 'POST' and not is_owner and form.is_valid():
        booking = handle_booking_submission(request, property, form)
        if booking:
            messages.success(request, 'Booking submitted! Awaiting confirmation.')
            return redirect('my_bookings')

    return render(request, 'property_detail.html', {
        'property': property,
        'form': form,
        'is_owner': is_owner,
        'booked_dates': booked_dates
    })



@login_required
def confirm_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    # Only the property owner can confirm
    if booking.booked_property.owner != request.user:
        raise PermissionDenied("You do not have permission to confirm this booking.")

    # Only allow confirmation if still pending
    if booking.status != 'pending':
        messages.warning(request, f"This booking is already {booking.status}.")
        return redirect('my_bookings')

    booking.status = 'confirmed'
    booking.save()

    messages.success(request, 'Booking confirmed successfully.')
    return redirect('my_bookings')

@login_required
def manage_property_view(request, pk=None):
    property = get_object_or_404(Property, pk=pk, owner=request.user) if pk else None
    form = PropertyForm(request.POST or None, request.FILES or None, instance=property)

    if request.method == 'POST' and form.is_valid():
        property = form.save(commit=False)
        if not property.pk:
            property.owner = request.user
        property.save()
        form.save_m2m()

        # Handle uploaded images
        images = request.FILES.getlist('images')
        for image in images:
            PropertyImage.objects.create(property_ref=property, image=image)


        return redirect('property_detail', pk=property.pk)

    return render(request, 'manage_property.html', {
        'form': form,
        'property': property
    })

@login_required
def my_bookings_view(request):
    user = request.user

    # Get all bookings where the user is the tenant or the property owner
    all_bookings = Booking.objects.select_related(
        'tenant', 'booked_property', 'booked_property__owner'
    ).filter(
        Q(tenant=user) | Q(booked_property__owner=user)
    )

    # Categorize for tabs
    bookings = all_bookings.filter(status__in=['pending', 'confirmed']).order_by('-start_date')
    past_bookings = all_bookings.filter(status='completed').order_by('-end_date')
    cancelled_bookings = all_bookings.filter(status='cancelled').order_by('-created_at')

    return render(request, 'my_bookings.html', {
        'bookings': bookings,
        'past_bookings': past_bookings,
        'cancelled_bookings': cancelled_bookings,
    })


@login_required
def my_properties_view(request):
    properties = Property.objects.filter(owner=request.user)
    return render(request, 'my_properties.html', {'properties': properties})



def search_view(request):
    query = request.GET.get('q', '')
    property_type = request.GET.get('property_type', '')
    location = request.GET.get('location', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort', '')

    # Base queryset
    properties = Property.objects.filter(is_available=True)

    # Search keyword
    if query:
        properties = properties.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(location__icontains=query)
        )

    # Filter by property type
    if property_type:
        properties = properties.filter(property_type=property_type)

    # Filter by location
    if location:
        properties = properties.filter(location__iexact=location)

    # Filter by price range
    if min_price:
        try:
            properties = properties.filter(price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            properties = properties.filter(price__lte=float(max_price))
        except ValueError:
            pass

    # Sorting
    if sort_by in ['price', '-price', 'created_at', '-created_at']:
        properties = properties.order_by(sort_by)
    else:
        properties = properties.order_by('-created_at')

    # Pagination (10 per page)
    paginator = Paginator(properties, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Dynamic filter options
    property_types = Property.PROPERTY_TYPE_CHOICES
    locations = Property.objects.values_list('location', flat=True).distinct()
    price_range = Property.objects.aggregate(min_price=Min('price'), max_price=Max('price'))

    context = {
        'properties': page_obj,
        'query': query,
        'property_types': property_types,
        'locations': locations,
        'price_range': price_range,
        'search_params': request.GET,  # for pre-filling form inputs
    }
    return render(request, 'search_results.html', context)


@login_required
@require_POST
def cancel_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if booking.tenant != request.user and booking.booked_property.owner != request.user:
        raise PermissionDenied("You are not allowed to cancel this booking.")

    if booking.status in ['cancelled', 'completed']:
        messages.warning(request, f"Cannot cancel a {booking.status} booking.")
        return redirect('my_bookings')

    # Get the cancellation reason from the form
    cancel_reason = request.POST.get('cancel_reason', '').strip()
    
    # Assign the reason and change status
    booking.cancel_reason = cancel_reason
    booking.status = 'cancelled'
    booking.save(update_fields=['status', 'cancel_reason'])

    # Mark the property available again
    booking.booked_property.is_available = True
    booking.booked_property.save(update_fields=['is_available'])

    messages.success(request, 'Booking has been cancelled successfully.')
    return redirect('my_bookings')

@login_required
def add_review_view(request, property_id):
    property = get_object_or_404(Property, id=property_id)
    if Review.objects.filter(user=request.user, property=property).exists():
        messages.warning(request, 'You have already reviewed this property.')
        return redirect('property_detail', pk=property.id)
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        Review.objects.create(property=property, user=request.user, rating=rating, comment=comment)
        messages.success(request, 'Your review has been submitted!')
        return redirect('property_detail', pk=property.id)
    return render(request, 'add_review.html', {'property': property})


@login_required
def upload_view(request):
    form = PropertyForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        property = form.save(commit=False)
        property.owner = request.user
        property.save()
        form.save_m2m()
        return redirect('property_detail', pk=property.id)
    return render(request, 'upload_property.html', {'form': form})

@login_required
def book_view(request, pk):
    property = get_object_or_404(Property, pk=pk)

    if property.owner == request.user:
        messages.error(request, "You cannot book your own property.")
        return redirect('property_detail', pk=pk)

    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        special_requests = request.POST.get('special_requests')

        booking = Booking(
            booked_property=property,
            tenant=request.user,
            start_date=start_date,
            end_date=end_date,
            special_requests=special_requests
        )

        try:
            booking.full_clean()
            booking.save()
            return redirect('booking_confirmation', booking_id=booking.id)
        except ValidationError as e:
            for field, error_list in e.message_dict.items():
                messages.error(request, f"{field}: {', '.join(error_list)}")

    return render(request, 'property_detail.html', {
        'property': property,
        'form': BookingForm(),
        'is_owner': False,
        'booked_dates': [],
    })

# Fixed booking_confirmation_view and related functions

@login_required
def booking_confirmation_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if booking.tenant != request.user:
        raise PermissionDenied("Only the booking tenant can pay.")

    if booking.status != 'pending':
        messages.info(request, f"This booking is already {booking.status}.")
        return redirect('my_bookings')

    if request.method == 'POST':
        form = PaymentForm(request.POST, request.FILES)
        if form.is_valid():
            payment_method = request.POST.get('payment_method')
            receipt = request.FILES.get('receipt')
            amount = booking.booked_property.price

            # Handle different payment methods
            if payment_method == 'mobile_money':
                success, txn_id = process_mobile_money_payment(request.user, amount)
                if success:
                    Payment.objects.create(
                        booking=booking,
                        amount=amount,
                        payment_method=payment_method,
                        transaction_id=txn_id,
                        is_successful=True,
                        receipt=receipt
                    )
                    # AUTO-CONFIRM BOOKING
                    booking.status = 'confirmed'
                    booking.save()
                    messages.success(request, 'Payment successful! Booking confirmed.')
                    return redirect('my_bookings')
                else:
                    messages.error(request, 'Mobile money payment failed. Try another method.')
                    
            elif payment_method == 'bank_transfer':
                success, txn_id = process_bank_transfer(request.user, amount)
                if success:
                    Payment.objects.create(
                        booking=booking,
                        amount=amount,
                        payment_method=payment_method,
                        transaction_id=txn_id,
                        is_successful=True,
                        receipt=receipt
                    )
                    # AUTO-CONFIRM BOOKING
                    booking.status = 'confirmed'
                    booking.save()
                    messages.success(request, 'Payment successful! Booking confirmed.')
                    return redirect('my_bookings')
                else:
                    messages.error(request, 'Bank transfer payment failed. Try another method.')
                    
            elif payment_method == 'credit_card':
                reference = f'BOOKING-{uuid.uuid4().hex[:10].upper()}'
                result = initialize_paystack_transaction(request.user.email, amount, reference)
                
                if result.get("status") is True:
                    # Create payment record (will be updated via webhook/verification)
                    Payment.objects.create(
                        booking=booking,
                        amount=amount,
                        payment_method='credit_card',
                        transaction_id=reference,
                        is_successful=False  # Will update after Paystack callback
                    )
                    return redirect(result["data"]["authorization_url"])
                else:
                    messages.error(request, "Failed to initialize Paystack transaction.")
    else:
        form = PaymentForm(initial={'amount': booking.booked_property.price})

    return render(request, 'booking_confirmation.html', {
        'booking': booking,
        'form': form,
    })


@login_required
@csrf_exempt
def paystack_verify_view(request, reference):
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    try:
        response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as e:
        messages.error(request, f"Error verifying payment: {e}")
        return redirect('my_bookings')

    if result.get("status") and result.get("data", {}).get("status") == "success":
        try:
            payment = Payment.objects.get(transaction_id=reference)

            if payment.is_successful:
                messages.info(request, "This payment was already verified.")
            else:
                # Update payment status
                payment.is_successful = True
                payment.save()

                # AUTO-CONFIRM BOOKING
                booking = payment.booking
                booking.status = 'confirmed'
                booking.save()

                # Optional: Mark property as unavailable for the booking period
                # This depends on your business logic
                # booking.booked_property.is_available = False
                # booking.booked_property.save()

                messages.success(request, "Payment verified and booking confirmed!")
        except Payment.DoesNotExist:
            messages.error(request, "Payment record not found.")
    else:
        messages.error(request, "Payment verification failed.")

    return redirect('my_bookings')


@csrf_exempt
def paystack_webhook_view(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid method")

    signature = request.headers.get('x-paystack-signature')
    body = request.body
    computed_signature = hmac.new(
        key=bytes(settings.PAYSTACK_SECRET_KEY, 'utf-8'),
        msg=body,
        digestmod=hashlib.sha512
    ).hexdigest()

    if signature != computed_signature:
        logger.warning("Invalid webhook signature")
        return HttpResponseBadRequest("Invalid signature")

    try:
        payload = json.loads(body)
        event = payload.get('event')
        data = payload.get('data', {})

        if event == 'charge.success':
            reference = data.get('reference')

            try:
                payment = Payment.objects.get(transaction_id=reference)
                if not payment.is_successful:
                    # Update payment status
                    payment.is_successful = True
                    payment.save()

                    # AUTO-CONFIRM BOOKING
                    booking = payment.booking
                    booking.status = 'confirmed'
                    booking.save()

                    # Optional: Update property availability
                    # booking.booked_property.is_available = False
                    # booking.booked_property.save()

                    logger.info(f"Payment verified and booking confirmed via webhook: {reference}")
                else:
                    logger.info(f"Payment already processed: {reference}")
            except Payment.DoesNotExist:
                logger.warning(f"Payment with reference {reference} not found.")
                
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        return HttpResponseBadRequest("Invalid JSON")
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return HttpResponseBadRequest("Processing error")

    return JsonResponse({'status': 'success'})


# Helper function to create missing payment processing functions
def process_mobile_money_payment(user, amount):
    """
    Simulate mobile money payment processing
    Replace with actual mobile money API integration
    """
    try:
        # Simulate API call to mobile money provider
        # In reality, you'd integrate with providers like MTN, Vodafone, etc.
        
        # For demo purposes, assume success
        transaction_id = f'MM-{uuid.uuid4().hex[:10].upper()}'
        
        # Here you would make actual API calls to mobile money provider
        # response = mobile_money_api.charge(user.phone, amount)
        
        return True, transaction_id
    except Exception as e:
        logger.error(f"Mobile money payment failed: {e}")
        return False, None


def process_bank_transfer(user, amount):
    """
    Simulate bank transfer payment processing
    Replace with actual bank API integration
    """
    try:
        # Simulate bank transfer processing
        # In reality, you'd integrate with bank APIs
        
        transaction_id = f'BT-{uuid.uuid4().hex[:10].upper()}'
        
        # Here you would make actual API calls to bank
        # response = bank_api.process_transfer(user.account, amount)
        
        return True, transaction_id
    except Exception as e:
        logger.error(f"Bank transfer failed: {e}")
        return False, None


# Additional helper function for manual confirmation (if needed)
@login_required
def manual_confirm_booking_view(request, booking_id):
    """
    Allow property owners to manually confirm bookings
    (useful as backup or for special cases)
    """
    booking = get_object_or_404(Booking, id=booking_id)

    # Only the property owner can manually confirm
    if booking.booked_property.owner != request.user:
        raise PermissionDenied("You do not have permission to confirm this booking.")

    # Only allow confirmation if still pending
    if booking.status != 'pending':
        messages.warning(request, f"This booking is already {booking.status}.")
        return redirect('my_bookings')

    booking.status = 'confirmed'
    booking.save()

    messages.success(request, 'Booking confirmed manually.')
    return redirect('my_bookings')
# Add these missing views to your views.py file

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime, date

# ============================
# 🔹 MISSING CRITICAL VIEWS
# ============================

@login_required
def booking_success_view(request, booking_id):
    """
    Success page after payment completion
    Shows booking confirmation details
    """
    booking = get_object_or_404(Booking, id=booking_id, tenant=request.user)
    
    # Check if booking was confirmed
    if booking.status == 'confirmed':
        messages.success(request, 'Your booking has been confirmed! Payment was successful.')
    elif booking.status == 'pending':
        messages.info(request, 'Your booking is pending confirmation. Payment verification in progress.')
    else:
        messages.warning(request, f'Booking status: {booking.get_status_display()}')
    
    return render(request, 'success.html', {
        'booking': booking,
        'payment': getattr(booking, 'payment', None)
    })


@csrf_exempt
def paystack_callback_view(request):
    """
    Handle Paystack payment callback
    This is where users are redirected after payment
    """
    reference = request.GET.get('reference')
    
    if not reference:
        messages.error(request, "Invalid payment reference.")
        return redirect('my_bookings')
    
    # Verify the payment
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }
    
    try:
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}", 
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") and result.get("data", {}).get("status") == "success":
            try:
                payment = Payment.objects.get(transaction_id=reference)
                
                if not payment.is_successful:
                    # Mark payment as successful - this triggers auto-confirmation
                    payment.verify_payment()  # This method also confirms the booking
                    
                    messages.success(request, "Payment successful! Your booking has been confirmed.")
                else:
                    messages.info(request, "Payment already processed.")
                    
                return redirect('booking_success', booking_id=payment.booking.id)
                
            except Payment.DoesNotExist:
                messages.error(request, "Payment record not found.")
        else:
            messages.error(request, "Payment verification failed.")
            
    except requests.RequestException as e:
        messages.error(request, f"Error verifying payment: {e}")
    
    return redirect('my_bookings')


@login_required
@require_http_methods(["POST"])
def mobile_money_callback_view(request):
    """
    Handle mobile money payment callback
    """
    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        status = data.get('status')
        
        if transaction_id and status == 'success':
            try:
                payment = Payment.objects.get(transaction_id=transaction_id)
                if not payment.is_successful:
                    payment.verify_payment()  # Auto-confirms booking
                    return JsonResponse({'status': 'success', 'message': 'Payment verified'})
                else:
                    return JsonResponse({'status': 'info', 'message': 'Already processed'})
                    
            except Payment.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Payment not found'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Payment failed'})
            
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'status': 'error', 'message': 'Invalid data'})


@login_required
def bank_transfer_verify_view(request, payment_id):
    """
    Manual verification for bank transfers
    Usually done by admin after checking bank statement
    """
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Only allow property owner or admin to verify
    if not (request.user.is_staff or payment.booking.booked_property.owner == request.user):
        raise PermissionDenied("You don't have permission to verify this payment.")
    
    if request.method == 'POST' and not payment.is_successful:
        payment.verify_payment()  # Auto-confirms booking
        messages.success(request, 'Payment verified and booking confirmed!')
    
    return redirect('my_bookings')


# ============================
# 🔹 AJAX UTILITY VIEWS
# ============================

@require_http_methods(["POST"])
def check_availability_ajax(request):
    """
    AJAX endpoint to check property availability for given dates
    """
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
        
        property_obj = get_object_or_404(Property, id=property_id)
        
        # Check for overlapping confirmed bookings
        is_available = not property_obj.has_confirmed_bookings_for_dates(start_date, end_date)
        
        # Get booked dates for calendar display
        bookings = property_obj.bookings.filter(status='confirmed')
        booked_dates = []
        for booking in bookings:
            current_date = booking.start_date
            while current_date <= booking.end_date:
                booked_dates.append(current_date.strftime('%Y-%m-%d'))
                current_date += timezone.timedelta(days=1)
        
        return JsonResponse({
            'available': is_available,
            'booked_dates': booked_dates,
            'message': 'Available' if is_available else 'Property is already booked for these dates'
        })
        
    except (json.JSONDecodeError, ValueError, KeyError):
        return JsonResponse({'error': 'Invalid data'}, status=400)


@require_http_methods(["POST"])
def calculate_price_ajax(request):
    """
    AJAX endpoint to calculate total price for booking
    """
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
        
        property_obj = get_object_or_404(Property, id=property_id)
        
        # Create temporary booking object to calculate price
        temp_booking = Booking(
            booked_property=property_obj,
            start_date=start_date,
            end_date=end_date
        )
        
        total_price = temp_booking.total_price
        duration = temp_booking.duration
        
        return JsonResponse({
            'total_price': float(total_price),
            'duration': duration,
            'price_per_day': float(property_obj.price),
            'property_type': property_obj.property_type
        })
        
    except (json.JSONDecodeError, ValueError, KeyError):
        return JsonResponse({'error': 'Invalid data'}, status=400)


# ============================
# 🔹 PROPERTY IMAGE MANAGEMENT
# ============================

@login_required
@require_http_methods(["POST"])
def upload_property_images(request, property_id):
    """
    Upload additional images to a property
    """
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    
    images = request.FILES.getlist('images')
    uploaded_count = 0
    
    for image in images:
        PropertyImage.objects.create(property_ref=property_obj, image=image)
        uploaded_count += 1
    
    messages.success(request, f'Successfully uploaded {uploaded_count} images.')
    return redirect('property_detail', pk=property_id)


@login_required
@require_http_methods(["POST"])
def delete_property_image(request, image_id):
    """
    Delete a property image
    """
    image = get_object_or_404(PropertyImage, id=image_id)
    
    # Check ownership
    if image.property_ref.owner != request.user:
        raise PermissionDenied("You don't own this property.")
    
    property_id = image.property_ref.id
    image.delete()
    
    messages.success(request, 'Image deleted successfully.')
    return redirect('property_detail', pk=property_id)


@login_required
@require_http_methods(["POST"])
def set_primary_image(request, image_id):
    """
    Set an image as primary for a property
    """
    image = get_object_or_404(PropertyImage, id=image_id)
    
    # Check ownership
    if image.property_ref.owner != request.user:
        raise PermissionDenied("You don't own this property.")
    
    # Set as primary (this automatically unsets other primary images)
    image.is_primary = True
    image.save()
    
    messages.success(request, 'Primary image updated.')
    return redirect('property_detail', pk=image.property_ref.id)


# ============================
# 🔹 IMPROVED BOOKING SUBMISSION HANDLER
# ============================

def handle_booking_submission(request, property_obj, form):
    """
    Helper function to handle booking form submission
    Returns booking object if successful, None if failed
    """
    try:
        booking = form.save(commit=False)
        booking.booked_property = property_obj
        booking.tenant = request.user
        
        # Validate the booking
        booking.full_clean()
        booking.save()
        
        return booking
        
    except ValidationError as e:
        for field, errors in e.message_dict.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return None