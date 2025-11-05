from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('authapp.urls')),
]

if settings.DEBUG:
    # Serve static files during development. Don't index into
    # STATICFILES_DIRS[0] directly — it may be empty. Prefer STATIC_ROOT
    # or BASE_DIR / 'static' as a fallback.
    # static_doc_root = None
    # if getattr(settings, 'STATICFILES_DIRS', None):
    #     try:
    #         if len(settings.STATICFILES_DIRS) > 0:
    #             static_doc_root = settings.STATICFILES_DIRS[0]
    #     except Exception:
    #         static_doc_root = None

    # if not static_doc_root and getattr(settings, 'STATIC_ROOT', None):
    #     static_doc_root = settings.STATIC_ROOT

    # if not static_doc_root and getattr(settings, 'BASE_DIR', None):
    #     static_doc_root = settings.BASE_DIR / 'static'

    # if static_doc_root:
    #     urlpatterns += static(settings.STATIC_URL, document_root=static_doc_root)

    # Serve media files during development if configured
    if getattr(settings, 'MEDIA_URL', None) and getattr(settings, 'MEDIA_ROOT', None):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)