from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, PropertyViewSet, BookingViewSet, 
    PaymentViewSet, ReviewViewSet, AmenityViewSet,
    PropertyImageViewSet
)
from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views
from .views import booking_confirmation_view
from .views import paystack_webhook_view
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
    # ✅ API endpoints
    path('api/', include(router.urls)),
    
    # ✅ Frontend views
    path('', views.index_view, name='index'),
     path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),

    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Property views
    path('properties/', views.search_view, name='search'),
    path('properties/<int:pk>/', views.property_detail_view, name='property_detail'),
    path('properties/upload/', views.manage_property_view, name='upload'),
    path('properties/manage/<int:pk>/', views.manage_property_view, name='manage_property'),
    path('properties/my-properties/', views.my_properties_view, name='my_properties'),
    
    # Booking views
    path('properties/<int:pk>/book/', views.book_view, name='book'),
    path('bookings/', views.my_bookings_view, name='my_bookings'),
     path('bookings/<int:booking_id>/confirm/', views.confirm_booking_view, name='confirm_booking'),
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking_view, name='cancel_booking'),
    
    # Review views
    path('properties/<int:property_id>/review/', views.add_review_view, name='add_review'),
    
    # Password reset views (if needed)
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
     path('booking/<int:booking_id>/confirmed/', booking_confirmation_view, name='booking_confirmation'),
     path('paystack/verify/<str:reference>/', views.paystack_verify_view, name='paystack_verify'),
     path('paystack/webhook/', paystack_webhook_view, name='paystack_webhook'),


]