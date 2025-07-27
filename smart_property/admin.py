from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Property, Booking, Payment, Review, Amenity, PropertyImage

class CustomUserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'role')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone_number', 'profile_picture')}),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('role', 'phone_number', 'profile_picture'),
        }),
    )

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('amount', 'payment_method', 'transaction_id', 'is_successful')
    can_delete = False

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'property_type', 'location', 'price', 'is_available', 'created_at')
    list_filter = ('property_type', 'is_available', 'created_at')
    search_fields = ('title', 'location', 'description')
    raw_id_fields = ('owner',)
    filter_horizontal = ('amenities',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('owner', 'title', 'description', 'price')
        }),
        ('Details', {
            'fields': ('property_type', 'location', 'address', 'amenities', 'is_available')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'booked_property', 'tenant', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'booked_property__property_type')
    search_fields = ('booked_property__title', 'tenant__username')
    raw_id_fields = ('booked_property', 'tenant')
    inlines = [PaymentInline]

    readonly_fields = ('created_at',)  # <-- Add this line

    fieldsets = (
        (None, {
            'fields': ('booked_property', 'tenant', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'created_at')  # This is now safe
        }),
        ('Details', {
            'fields': ('special_requests',)
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'amount', 'payment_method', 'is_successful', 'created_at')
    list_filter = ('payment_method', 'is_successful', 'created_at')
    search_fields = ('booking__property__title', 'booking__tenant__username')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('booking', 'amount', 'payment_method', 'is_successful')
        }),
        ('Receipt', {
            'fields': ('receipt',)
        }),
        ('Date', {
            'fields': ('created_at',)
        }),
    )

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('property', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('property__title', 'user__username', 'comment')

@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)

@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property_ref', 'is_primary')
    list_filter = ('is_primary',)
    raw_id_fields = ('property_ref',)

admin.site.register(User, CustomUserAdmin)