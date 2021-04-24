from Trader import Trader
from traderboard.models import Profile, TradingAccount
from traderboard.forms import \
    AddTradingAccountForm, EditProfileForm, RegistrationForm, EditSettingsForm, ProfileFilterForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.template.context_processors import csrf
from datetime import datetime, timedelta, timezone
from verify_email.email_handler import send_verification_email
import time

def home_out(request):
    '''home page for visitors'''
    order_by = request.GET.get('order_by', 'daily_pnl')
    traders = enumerate(Profile.objects.order_by(order_by).reverse(), start=1)
    return render(request, 'index.html', {'traders': traders})


@login_required
def home(request):
    '''home page for logged in users'''
    user = request.user
    order_by = request.GET.get('order_by', 'daily_pnl')
    traders = enumerate(Profile.objects.order_by(order_by).reverse(), start=1)
    return render(request, 'index.html', {'traders': traders, 'user': user})


def register(request):
    args = {}
    args.update(csrf(request))
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        args['form'] = form
        if form.is_valid():
            inactive_user = send_verification_email(request, form)
            return render(request, 'accounts/activate_account_done.html')
        else:
            return render(request, 'accounts/register.html', args)
    else:
        args['form'] = RegistrationForm()
        return render(request, 'accounts/register.html', args)


@login_required
def show_profile(request):
    user = User.objects.get(pk=request.user.id)
    trader = Trader(user)
    if request.method == 'GET':
        form = ProfileFilterForm(request.GET)
        if form.is_valid():
            t = time.time()
            profile = trader.get_profile(form.cleaned_data['date_from'], form.cleaned_data['date_to'], 'USDT', False)
            print(time.time() - t)
        else:
            profile = trader.get_profile(datetime.now(timezone.utc) - timedelta(days=7), 
                                                datetime.now(timezone.utc), 'USDT', False)
    return render(request, 'accounts/profile.html', profile)


@login_required
def show_overview_profile(request, pk=None):
    user = get_object_or_404(User, pk=pk)
    trader = Trader(user)
    if request.method == 'GET':
        form = ProfileFilterForm(request.GET)
        if form.is_valid():
            profile = trader.get_profile(form['date_from'].value(), form['date_to'].value(), 'USDT', not user.profile.public)
        else:
            profile = trader.get_profile(datetime.now(timezone.utc) - timedelta(days=7),
                                                 datetime.now(timezone.utc), 'USDT', not user.profile.public)
    return render(request, 'accounts/profile.html', profile)


@login_required
def show_settings(request):
    return redirect('edit_profile')


@login_required
def edit_settings(request):
    user = User.objects.get(pk=request.user.id)
    args = {}
    args.update(csrf(request))
    args['user'] = user
    if request.method == 'POST':
        form = EditSettingsForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('edit_settings')
        else:
            messages.error(request, 'Invalid information provided.')
            return redirect('edit_settings')
    else:
        form = EditSettingsForm(instance=user)
        args['form'] = form
        return render(request, 'accounts/edit_settings.html', args)


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
            messages.success(request, 'Profile succesfully updated!')
            return redirect('edit_profile')
        else:
            messages.error(request, 'Invalid information provided.')
            return redirect('edit_profile')
    else:
        form = EditProfileForm(instance=user)
        args['form'] = form
        return render(request, 'accounts/edit_profile.html', args)


@login_required
def edit_password(request):
    args = {}
    args.update(csrf(request))
    if request.method == 'POST':
        form = PasswordChangeForm(data=request.POST, user=request.user)
        form.actual_user = request.user
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Password changed successfully!')
            return redirect('edit_password')
        else:
            messages.error(request, 'Invalid password.')
            return redirect('edit_password')
    else:
        form = PasswordChangeForm(user=request.user)
        args['form'] = form
        return render(request, 'accounts/edit_password.html', args)


@login_required
def show_trading_accounts(request):
    args = {}
    tas = TradingAccount.objects.filter(user=request.user)
    args['tas'] = tas
    return render(request, 'accounts/trading_accounts.html', args)


@login_required
def add_trading_account(request):
    user = User.objects.get(pk=request.user.id)
    args = {}
    args.update(csrf(request))
    args['user'] = user
    if request.method == 'POST':
        form = AddTradingAccountForm(data=request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Trading account added successfully!')
            return redirect('trading_accounts')
        else:
            messages.error(request, 'Invalid API information.')
            return redirect('add_trading_account')
    else:
        form = AddTradingAccountForm(user=request.user)
        args['form'] = form
        return render(request, 'accounts/add_trading_account.html', args)


@login_required
def remove_trading_account(request, pk=None):
    ta = get_object_or_404(TradingAccount, user=request.user, pk=pk)
    if ta:
        ta.delete()
        messages.success(request, 'Trading account succesfully removed.')
    return redirect('trading_accounts')