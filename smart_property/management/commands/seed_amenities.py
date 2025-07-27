from django.core.management.base import BaseCommand
from smart_property.models import Amenity

class Command(BaseCommand):
    help = 'Seed the database with common property amenities'

    def handle(self, *args, **kwargs):
        amenities = [
            ('WiFi', 'wifi'),
            ('Air Conditioning', 'snowflake'),
            ('TV', 'tv'),
            ('Swimming Pool', 'swimming-pool'),
            ('Parking', 'car'),
            ('Kitchen', 'utensils'),
            ('Washing Machine', 'soap'),
            ('Gym', 'dumbbell'),
            ('Security', 'shield-alt'),
            ('Balcony', 'building'),
            ('Pet Friendly', 'dog'),
            ('Water Heater', 'hot-tub'),
            ('Electricity', 'bolt'),
            ('Furnished', 'couch'),
        ]

        for name, icon in amenities:
            obj, created = Amenity.objects.update_or_create(
                name=name,
                defaults={'icon': icon}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Created amenity: {name}'))
            else:
                self.stdout.write(self.style.WARNING(f'ℹ️ Updated or exists: {name}'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Amenity seeding complete.\n'))
