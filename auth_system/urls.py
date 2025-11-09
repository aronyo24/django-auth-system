from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # django-allauth URLs (login, logout, social account flows)
    path('account/', include('allauth.urls')),
    path('', include('authapp.urls')),
]

if settings.DEBUG:
   
    if getattr(settings, 'MEDIA_URL', None) and getattr(settings, 'MEDIA_ROOT', None):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)