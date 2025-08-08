from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, PropertyViewSet, BookingViewSet,
    PaymentViewSet, ReviewViewSet, AmenityViewSet,
    PropertyImageViewSet
)
from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

# Register API endpoints
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'properties', PropertyViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'amenities', AmenityViewSet)
router.register(r'property-images', PropertyImageViewSet)


urlpatterns = [
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    path('register/', views.register_view, name='register'),
    
    # Password reset views
    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='password_reset.html'),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),
         name='password_reset_complete'),
    
    # ============================
    # 🔹 MAIN FRONTEND VIEWS
    # ============================
    path('', views.index_view, name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('search/', views.search_view, name='search'),
    
    # ============================
    # 🔹 PROPERTY VIEWS
    # ============================
    path('properties/<int:pk>/', views.property_detail_view, name='property_detail'),
    path('properties/upload/', views.manage_property_view, name='upload'),
    path('properties/manage/<int:pk>/', views.manage_property_view, name='manage_property'),
    path('properties/my-properties/', views.my_properties_view, name='my_properties'),
    
    # ============================
    # 🔹 BOOKING VIEWS (CRITICAL FOR AUTO-CONFIRMATION)
    # ============================
    # Step 1: Book property
    path('properties/<int:pk>/book/', views.book_view, name='book'),
    
    # Step 2: Payment and confirmation (THIS IS THE KEY URL)
    path('bookings/<int:booking_id>/payment/', views.booking_confirmation_view, name='booking_confirmation'),
    
    # Step 3: Payment success/verification
    path('bookings/<int:booking_id>/success/', views.booking_success_view, name='booking_success'),
    
    # Booking management
    path('bookings/', views.my_bookings_view, name='my_bookings'),
    path('bookings/<int:booking_id>/confirm/', views.confirm_booking_view, name='confirm_booking'),  # Manual confirmation
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking_view, name='cancel_booking'),
    
    # ============================
    # 🔹 PAYMENT PROCESSING URLS (CRITICAL)
    # ============================
    # Paystack integration
    path('payments/paystack/verify/<str:reference>/', views.paystack_verify_view, name='paystack_verify'),
    path('payments/paystack/webhook/', views.paystack_webhook_view, name='paystack_webhook'),
    path('payments/paystack/callback/', views.paystack_callback_view, name='paystack_callback'),
    
    # Mobile Money endpoints (if implemented)
    path('payments/mobile-money/callback/', views.mobile_money_callback_view, name='mobile_money_callback'),
    
    # Bank transfer verification (if implemented)
    path('payments/bank-transfer/verify/<int:payment_id>/', views.bank_transfer_verify_view, name='bank_transfer_verify'),
    
    # ============================
    # 🔹 REVIEW VIEWS
    # ============================
    path('properties/<int:property_id>/review/', views.add_review_view, name='add_review'),
    
    # ============================
    # 🔹 ADDITIONAL UTILITY VIEWS
    # ============================
    # AJAX endpoints for dynamic features
    path('ajax/check-availability/', views.check_availability_ajax, name='check_availability_ajax'),
    path('ajax/calculate-price/', views.calculate_price_ajax, name='calculate_price_ajax'),
    
    # Property image management
    path('properties/<int:property_id>/images/upload/', views.upload_property_images, name='upload_property_images'),
    path('images/<int:image_id>/delete/', views.delete_property_image, name='delete_property_image'),
    path('images/<int:image_id>/set-primary/', views.set_primary_image, name='set_primary_image'),
    path('properties/', views.property_list_view, name='property_list'),
    path('property/delete/<int:pk>/', views.delete_property, name='delete_property'),

]