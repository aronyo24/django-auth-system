from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from .models import UserProfile


class EmailVerificationRequiredMiddleware:
    """Block authenticated users from accessing the app until email verification."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_view_names = {
            'login',
            'logout',
            'register',
            'activate',
            'verify_otp',
            'resend_otp',
            'forgot_password',
            'password_reset_verify',
        }

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = self._get_or_create_profile(request)
            if profile and not profile.email_verified:
                if not self._path_is_exempt(request):
                    request.session['pending_user_id'] = request.user.pk
                    if request.path != reverse('verify_otp'):
                        messages.warning(request, 'Please verify your email to continue.')
                    return redirect('verify_otp')
                if request.resolver_match and request.resolver_match.view_name == 'verify_otp':
                    request.session['pending_user_id'] = request.user.pk

        response = self.get_response(request)
        return response

    def _path_is_exempt(self, request):
        match = request.resolver_match
        if not match:
            try:
                match = resolve(request.path_info)
            except Resolver404:
                match = None

        if match and match.view_name in self.allowed_view_names:
            return True

        if match and match.namespace == 'admin':
            return True

        static_url = getattr(settings, 'STATIC_URL', None) or ''
        media_url = getattr(settings, 'MEDIA_URL', None) or ''
        if static_url and request.path.startswith(static_url):
            return True
        if media_url and request.path.startswith(media_url):
            return True

        return False

    @staticmethod
    def _get_or_create_profile(request):
        try:
            return request.user.profile
        except UserProfile.DoesNotExist:
            return UserProfile.objects.create(user=request.user)

