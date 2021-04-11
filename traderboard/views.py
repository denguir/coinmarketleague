from Trader import Trader
from Market import Market
from traderboard.models import Profile, SnapshotProfile, SnapshotProfileDetails
from traderboard.forms import AddTradingAccountForm, EditProfileForm, RegistrationForm
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.template.context_processors import csrf
from verify_email.email_handler import send_verification_email
from datetime import datetime, timedelta, timezone
from utils import to_series, to_time_series


__PLATFORMS__ = ['Binance']


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


def register(request):
    args = {}
    args.update(csrf(request))
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        args['form'] = form
        if form.is_valid():
            form.save()
            return redirect('home')
        else:
            return render(request, 'accounts/register.html', args)
    else:
        args['form'] = RegistrationForm()
        return render(request, 'accounts/register.html', args)


# see: https://pypi.org/project/Django-Verify-Email/
# def register(request):
#     args = {}
#     args.update(csrf(request))
#     if request.method == 'POST':
#         form = RegistrationForm(request.POST)
#         args['form'] = form
#         if form.is_valid():
#             inactive_user = send_verification_email(request, form)
#             return redirect('home')
#         else:
#             return render('accounts/register.html', args)
#     else:
#         args['form'] = RegistrationForm()
#         return render('accounts/register.html', args)


@login_required
def show_profile(request):
    user = User.objects.get(pk=request.user.id)
    markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}
    trader = Trader(user, markets)
    now = datetime.now(timezone.utc)

    # get balance aggregated history
    balance_usdt_hist = trader.get_historical_balances(now - timedelta(days=31), now, 'USDT')
    balance_usdt_hist = to_time_series(balance_usdt_hist)

    # get balance info now
    balance_usdt = round(trader.get_balances_value('USDT'), 2)

    # get balance percentage
    balance_percentage = trader.get_relative_balances('USDT')
    balance_percentage = to_series(balance_percentage)

    # get balance details info
    balance_details = trader.get_balances()
    balance_details = to_series(balance_details)

    # get PnL aggregated history
    cum_pnl_usdt_hist = trader.get_historical_cumulative_PnL(now - timedelta(days=31), now, 'USDT')
    cum_pnl_usdt_hist = to_time_series(cum_pnl_usdt_hist)
    

    args = {'user': user, 'balance_usdt': balance_usdt, 'balance_details': balance_details,
            'balance_usdt_hist': balance_usdt_hist, 'balance_percentage': balance_percentage, 
            'cum_pnl_usdt_hist': cum_pnl_usdt_hist, 'overview': False}

    return render(request, 'accounts/profile.html', args)


@login_required
def show_overview_profile(request, pk=None):
    if pk:
        user = User.objects.get(pk=pk)
        if user.profile.public:
            overview = False
        else:
            overview = True
    else:
        return render(request, '404.html')
    
    markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}
    trader = Trader(user, markets)
    now = datetime.now(timezone.utc)

    args = {'user': user, 'overview': overview}
    # get PnL aggregated history
    cum_pnl_usdt_hist = trader.get_historical_cumulative_PnL(now - timedelta(days=31), now, 'USDT')
    cum_pnl_usdt_hist = to_time_series(cum_pnl_usdt_hist)
    args['cum_pnl_usdt_hist'] = cum_pnl_usdt_hist
    # get balance percentage
    balance_percentage = trader.get_relative_balances('USDT')
    balance_percentage = to_series(balance_percentage)
    args['balance_percentage'] = balance_percentage

    if not overview:
        # get balance aggregated history
        balance_usdt_hist = trader.get_historical_balances(now - timedelta(days=31), now, 'USDT')
        balance_usdt_hist = to_time_series(balance_usdt_hist)
        args['balance_usdt_hist'] = balance_usdt_hist
        # get balance info now
        balance_usdt = round(trader.get_balances_value('USDT'), 2)
        args['balance_usdt'] = balance_usdt
        # get balance details info
        balance_details = trader.get_balances()
        balance_details = to_series(balance_details)
        args['balance_details'] = balance_details
    
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
            return redirect('edit_profile')
        else:
            return redirect('add_trading_account')
    else:
        form = AddTradingAccountForm(user=request.user)
        args['form'] = form
        return render(request, 'update_profile.html', args)

# TODO:
# for graphs, look at:
# https://simpleisbetterthancomplex.com/tutorial/2020/01/19/how-to-use-chart-js-with-django.html