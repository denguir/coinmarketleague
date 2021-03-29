from traderboard.models import Profile
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.models import User
from models import Profile
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render, redirect, render_to_response
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.template.context_processors import csrf
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib import messages
from tokens import account_activation_token
from forms import EditProfileForm, RegistrationForm


def home_out(request):
    # home page for logged out visitors
    order_by = request.GET.get('order_by', 'daily_pnl')
    traders = enumerate(Profile.objects.order_by(order_by).reverse(), start=1)
    return render(request, 'index.html', {'traders': traders})


@login_required
def home(request):
    # home page for logged in visitors
    user = request.user
    order_by = request.GET.get('order_by', 'daily_pnl')
    traders = enumerate(Profile.objects.order_by(order_by).reverse(), start=1)
    return render(request, 'index.html', {'traders': traders, 'user': user})

# complete urls, template:
# https://studygyaan.com/django/how-to-signup-user-and-send-confirmation-email-in-django     
def register(request):
    args = {}
    args.update(csrf(request))
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        args['form'] = form
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False # Deactivate account till it is confirmed
            user.save()

            current_site = get_current_site(request)
            subject = 'Activate your CoinMarketLeague account'
            message = render_to_string('emails/account_activation_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })
            user.email_user(subject, message)

            messages.success(request, ('Please confirm your email to complete registration.'))
            return redirect('home')
        else:
            return render_to_response('accounts/register.html', args)
    else:
        args['form'] = RegistrationForm()
        return render_to_response('accounts/register.html', args)


@login_required
def show_profile(request):
    trader = User.objects.get(pk=request.user.id)
    args = {'trader': trader, 'overview': False}
    return render(request, 'accounts/profile.html', args)


@login_required
def edit_profile(request):
    user = User.objects.get(pk=request.user.id)
    args = {}
    args.update(csrf(request))
    args['user'] = user
    if request.method == 'POST':
        form = EditProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return render(request, 'accounts/edit_profile.html', args)
    else:
        form = EditProfileForm(instance=user)
        args['form'] = form
        return render(request, 'accounts/edit_profile.html', args)


@login_required
def edit_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(data=request.POST, user=request.user)
        form.actual_user = request.user
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            return redirect('edit_profile')
        else:
            return redirect('edit_password')
    else:
        args = {}
        args.update(csrf(request))
        form = PasswordChangeForm(user=request.user)
        args['form'] = form
        return render(request, 'update_profile.html', args)

