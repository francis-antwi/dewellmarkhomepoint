from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Booking, Property


@receiver(post_save, sender=Booking)
def update_property_availability(sender, instance, **kwargs):
    if instance.status == 'confirmed':
        instance.property.is_available = False
    else:
        still_confirmed = Booking.objects.filter(property=instance.property, status='confirmed').exclude(id=instance.id).exists()
        instance.property.is_available = not still_confirmed
    instance.property.save()


@receiver(post_delete, sender=Booking)
def restore_property_availability(sender, instance, **kwargs):
    if instance.status == 'confirmed':
        still_confirmed = Booking.objects.filter(property=instance.property, status='confirmed').exists()
        instance.property.is_available = not still_confirmed
        instance.property.save()
