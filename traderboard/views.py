from Trader import Trader
from traderboard.models import Profile, TradingAccount
from django.contrib.auth.models import User
from traderboard.forms import \
    AddTradingAccountForm, EditProfileForm, RegistrationForm, EditSettingsForm, ProfileFilterForm
from django.contrib.auth.forms import PasswordChangeForm
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template.context_processors import csrf
from django.db.models import F
from verify_email.email_handler import send_verification_email
from datetime import datetime, timedelta, timezone
from .tasks import load_account_history


def home_out(request):
    '''home page for visitors'''
    order_by = request.GET.get('order_by', 'daily_pnl')
    traders = enumerate(Profile.objects.order_by(F('daily_pnl').desc(nulls_last=True),
                                                 F('weekly_pnl').desc(nulls_last=True),
                                                 F('monthly_pnl').desc(nulls_last=True),   
                                                 ), start=1)
    return render(request, 'index.html', {'traders': traders})


@login_required
def home(request):
    '''home page for logged in users'''
    user = request.user
    order_by = request.GET.get('order_by', 'daily_pnl')
    traders = enumerate(Profile.objects.order_by(F('daily_pnl').desc(nulls_last=True),
                                                 F('weekly_pnl').desc(nulls_last=True),
                                                 F('monthly_pnl').desc(nulls_last=True),   
                                                 ), start=1)
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
    req_profile = Profile.objects.get(user=user)
    trader = Trader(user)
    if request.method == 'GET':
        if req_profile.nacc > 0:
            form = ProfileFilterForm(request.GET)
            if form.is_valid():
                profile = trader.get_profile(form.cleaned_data['date_from'], 
                                             form.cleaned_data['date_to'], 
                                             'USDT', 
                                             False)
            else:
                # by default, show last week stats
                now = datetime.now(timezone.utc)
                date_from = datetime.combine(now - timedelta(days=7), datetime.min.time(), timezone.utc)
                date_to = datetime.combine(now, datetime.max.time(), timezone.utc)
                profile = trader.get_profile(date_from, date_to, 'USDT', False)
        else:
            profile = {'overview': False, 'trader': user}
            messages.info(request, 'You have no trading account linked to your profile.\n\
                                    Upgrade your profile on Settings > Link trading account to have your own dashboard !')
        profile['user'] = request.user
        return render(request, 'accounts/profile.html', profile)


@login_required
def show_overview_profile(request, pk=None):
    user = get_object_or_404(User, pk=pk)
    trader = Trader(user)
    req_profile = Profile.objects.get(user=request.user)
    if request.method == 'GET':
        if req_profile.nacc > 0:
            form = ProfileFilterForm(request.GET)
            if form.is_valid():
                profile = trader.get_profile(form.cleaned_data['date_from'], 
                                             form.cleaned_data['date_to'], 
                                             'USDT', 
                                             not user.profile.public)
            else:
                # by default, show last week stats
                # by default, show last week stats
                now = datetime.now(timezone.utc)
                date_from = datetime.combine(now - timedelta(days=7), datetime.min.time(), timezone.utc)
                date_to = datetime.combine(now, datetime.max.time(), timezone.utc)
                profile = trader.get_profile(date_from, date_to, 'USDT', not user.profile.public)
        else:
            profile = {'overview': True, 'trader': user}
            messages.info(request, 'You have no trading account linked to your profile.\n\
                                    Upgrade your profile on Settings > Link trading account to be able to inspect others dashboard !')
        
        profile['user'] = request.user
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
        form = EditSettingsForm(request.POST, request.FILES, instance=user)
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
        u_form = EditProfileForm(request.POST, instance=user)
        if u_form.is_valid():
            u_form.save()
            messages.success(request, 'Profile succesfully updated!')
        else:
            print(u_form.errors)
            messages.error(request, 'Invalid information provided.')

        return redirect('edit_profile')
    else:
        u_form = EditProfileForm(instance=user)
        args['u_form'] = u_form
        return render(request, 'accounts/edit_profile.html', args)


# @login_required
# def edit_profile(request):
#     user = User.objects.get(pk=request.user.id)
#     args = {}
#     args.update(csrf(request))
#     args['user'] = user
#     if request.method == 'POST':
#         u_form = EditProfileForm(request.POST, instance=user)
#         p_form = EditSettingsForm(request.POST, request.FILES, instance=user.profile)
#         if u_form.is_valid() and p_form.is_valid():
#             u_form.save()
#             p_form.save()
#             messages.success(request, 'Profile succesfully updated!')
#         else:
#             print(u_form.errors)
#             print(p_form.errors)
#             messages.error(request, 'Invalid information provided.')

#         return redirect('edit_profile')
#     else:
#         u_form = EditProfileForm(instance=user)
#         p_form = EditSettingsForm(instance=user.profile)
#         args['u_form'] = u_form
#         args['p_form'] = p_form
#         return render(request, 'accounts/edit_profile.html', args)


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
    profile = Profile.objects.filter(user=user)
    args = {}
    args.update(csrf(request))
    args['user'] = user
    if request.method == 'POST':
        form = AddTradingAccountForm(data=request.POST, user=request.user)
        if form.is_valid():
            ta = form.save()
            messages.success(request, 'Trading account added successfully!')
            # load past data when adding a trading account
            try:
                load_account_history(user, ta)
                profile.update(nacc=F('nacc')+1)
                messages.success(request, 'Account synchronization success!')
            except Exception as e:
                print(e)
                messages.error(request, 'Account synchronization failed.')
            return redirect('trading_accounts')
        else:
            messages.error(request, 'Invalid API information. \n\
                Make sure your api keys are valid and not already used in another account.')
            return redirect('add_trading_account')
    else:
        form = AddTradingAccountForm(user=request.user)
        args['form'] = form
        return render(request, 'accounts/add_trading_account.html', args)


@login_required
def remove_trading_account(request, pk=None):
    ta = get_object_or_404(TradingAccount, user=request.user, pk=pk)
    profile = Profile.objects.filter(user=request.user)
    if ta:
        ta.delete()
        profile.update(nacc=F('nacc')-1)
        messages.success(request, 'Trading account succesfully removed.')
    return redirect('trading_accounts')


@login_required
def image_upload(request):
    if request.method == "POST" and request.FILES["image_file"]:
        image_file = request.FILES["image_file"]
        fs = FileSystemStorage()
        filename = fs.save(image_file.name, image_file)
        image_url = fs.url(filename)
        return render(request, "upload.html", {"image_url": image_url})
    return render(request, "upload.html")