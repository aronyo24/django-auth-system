from datetime import timedelta
import random

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import UserProfile

OTP_LENGTH = 6
OTP_EXPIRATION_MINUTES = 15
OTP_RESEND_WAIT_MINUTES = 5


def _issue_otp_and_send_email(request, user):
    """Generate a fresh OTP, email it with activation link, and return the code."""

    otp_code = f"{random.randint(0, 10 ** OTP_LENGTH - 1):0{OTP_LENGTH}d}"
    expires = timezone.now() + timedelta(minutes=OTP_EXPIRATION_MINUTES)

    current_site = get_current_site(request)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activate_link = request.build_absolute_uri(
        reverse('activate', kwargs={'uidb64': uid, 'token': token})
    )
    message = render_to_string(
        'activation_email.html',
        {
            'user': user,
            'activate_link': activate_link,
            'otp_code': otp_code,
            'domain': current_site.domain,
        },
    )
    email_msg = EmailMessage('Activate Your Account / OTP', message, to=[user.email])
    email_msg.content_subtype = 'html'
    email_msg.send()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.issue_otp(otp_code, UserProfile.REGISTRATION, expires)
    return otp_code


def home_view(request):
    return render(request, 'base.html')


def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if not all([first_name, last_name, username, email, password1, password2]):
            messages.error(request, 'All fields are required.')
            return redirect('register')

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('register')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )
        user.is_active = False
        user.save()
        display_name = f"{first_name} {last_name}".strip() or username
        UserProfile.objects.update_or_create(
            user=user,
            defaults={'display_name': display_name},
        )

        _issue_otp_and_send_email(request, user)

        # Save pending user id in session to allow OTP verification step
        request.session['pending_user_id'] = user.pk
        messages.success(request, 'Account created! Enter the OTP sent to your email to verify your account.')
        return redirect('verify_otp')

    return render(request, 'register.html')


def activate_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Your account has been activated! You can now log in.')
        return redirect('login')
    else:
        return render(request, 'activation_invalid.html')


def verify_otp_view(request):
    """Allow the user to submit the OTP code they received by email."""
    pending_user_id = request.session.get('pending_user_id')
    if not pending_user_id:
        messages.error(request, 'No pending verification found. Please register first.')
        return redirect('register')

    try:
        user = User.objects.get(pk=pending_user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please register again.')
        return redirect('register')

    if request.method == 'POST':
        code = request.POST.get('otp')
        if not code:
            messages.error(request, 'Please enter the OTP code.')
            return redirect('verify_otp')

        profile, _ = UserProfile.objects.get_or_create(user=user)

        if not profile.otp_matches(code):
            messages.error(request, 'Invalid OTP code.')
            return redirect('verify_otp')

        if profile.otp_is_expired():
            messages.error(request, 'OTP has expired. Use the resend option below to get a fresh code.')
            return redirect('verify_otp')

        # Mark user active and OTP used
        user.is_active = True
        user.save(update_fields=['is_active'])
        profile.mark_otp_used()
        profile.mark_email_verified()
        # Clear pending session
        request.session.pop('pending_user_id', None)

        messages.success(request, 'Your account has been verified! You can now log in.')
        return redirect('login')

    return render(request, 'otp_verify.html')


def resend_otp_view(request):
    if request.method != 'POST':
        return redirect('verify_otp')

    pending_user_id = request.session.get('pending_user_id')
    if not pending_user_id:
        messages.error(request, 'No pending verification found. Please register first.')
        return redirect('register')

    try:
        user = User.objects.get(pk=pending_user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please register again.')
        return redirect('register')

    if user.is_active:
        messages.info(request, 'Your account is already verified. You can log in.')
        return redirect('login')

    profile, _ = UserProfile.objects.get_or_create(user=user)
    now = timezone.now()
    if profile.last_otp_sent_at and (now - profile.last_otp_sent_at) < timedelta(minutes=OTP_RESEND_WAIT_MINUTES):
        messages.error(request, f'Please wait at least {OTP_RESEND_WAIT_MINUTES} minutes before requesting a new OTP.')
        return redirect('verify_otp')

    _issue_otp_and_send_email(request, user)
    messages.success(request, 'A new OTP has been sent to your email.')
    return redirect('verify_otp')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user:
            if not user.is_active:
                messages.error(request, 'Please activate your account first.')
                return redirect('login')
            login(request, user)
            messages.success(request, f'Welcome, {user.username}!')
            return redirect('/')
        else:
            messages.error(request, 'Invalid username or password.')
            return redirect('login')

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')
