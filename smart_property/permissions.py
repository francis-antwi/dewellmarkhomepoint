from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'tenant'):
            return obj.tenant == request.user
        
        return False


class IsBookingParticipant(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'booking'):
            booking = obj.booking
        else:
            booking = obj
        
        return (
            booking.tenant == request.user or
            booking.property.owner == request.user or
            request.user.is_staff
        )