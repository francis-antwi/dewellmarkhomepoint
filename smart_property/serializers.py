from rest_framework import serializers
from .models import (
    User, Property, Booking, 
    Payment, Review, Amenity,
    PropertyImage
)
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'phone_number', 'profile_picture']
        extra_kwargs = {
            'password': {'write_only': True},
            'profile_picture': {'required': False}
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', 'student'),
            phone_number=validated_data.get('phone_number', ''),
        )
        return user


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name', 'icon']


class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ['id', 'image', 'is_primary']


class PropertySerializer(serializers.ModelSerializer):
    amenities = AmenitySerializer(many=True, read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)
    owner = UserSerializer(read_only=True)
    
    class Meta:
        model = Property
        fields = [
            'id', 'title', 'description', 'price', 
            'property_type', 'location', 'address',
            'amenities', 'is_available', 'created_at',
            'updated_at', 'owner', 'images'
        ]


class BookingSerializer(serializers.ModelSerializer):
    property = PropertySerializer(read_only=True)
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.filter(is_available=True),
        write_only=True,
        source='property'
    )
    tenant = UserSerializer(read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'property', 'property_id', 'tenant',
            'start_date', 'end_date', 'status',
            'special_requests', 'created_at'
        ]
        read_only_fields = ['status', 'tenant', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'booking', 'amount', 'payment_method',
            'transaction_id', 'is_successful', 'created_at',
            'receipt'
        ]
        read_only_fields = ['is_successful', 'created_at']


class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'property', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['user', 'created_at']