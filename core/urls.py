from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('smart_property.urls')),
    path('api-auth/', include('rest_framework.urls')),  # browsable API login/logout
    path("__reload__/", include("django_browser_reload.urls")),
    path('', include('smart_property.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
