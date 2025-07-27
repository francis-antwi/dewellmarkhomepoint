from rest_framework.test import APITestCase
from django.urls import reverse
from .models import User, Property

class PropertyTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='pass', role='owner')
        self.client.login(username='test', password='pass')

    def test_create_property(self):
        url = reverse('property-list')
        data = {
            "title": "Test Property",
            "description": "A place",
            "price": 100.0,
            "property_type": "room",
            "location": "Campus",
            "owner": self.user.id
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
