import re
from django import forms
from django.contrib.auth import models
from django.contrib.auth.models import User
from traderboard.models import Profile, TradingAccount
from TradingClient import TradingClient
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from datetime import date, datetime, timezone
from django.utils.safestring import mark_safe

__PLATFORMS__ = ['Binance']


class RegistrationForm(UserCreationForm):
    username = forms.CharField(max_length=30, required=True)
    first_name = forms.CharField(max_length=30, required=False, help_text='Optional')
    last_name = forms.CharField(max_length=30, required=False, help_text='Optional')
    email = forms.EmailField(max_length=254, required=True, help_text='Enter a valid email address')

    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email'
        )
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(u'This username is already used. Please choose another one.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(u'This email address is already used. Please choose another one.')
        return email

    def save(self, commit=True):
        user = super(RegistrationForm, self).save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user    


class EditProfileForm(UserChangeForm):
    password = None
    # username = forms.CharField(max_length=30, disabled=False)
    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
        )


class EditSettingsForm(forms.ModelForm):
    picture = forms.ImageField(help_text='Max size: 1 MB')
    class Meta:
        model = Profile
        fields = ('picture', 
                  'public',)

    def clean_picture(self):
        picture = self.cleaned_data.get('picture', 0)
        if picture:
            if picture._size > 1024*1024:
                raise forms.ValidationError("Image file too large ( > 1MB).")
            return picture
        else:
            raise forms.ValidationError("Couldn't read uploaded image.")


class AddTradingAccountForm(forms.ModelForm):
    '''Form to link a trading account to your profile'''

    CHOICES = [("Binance", "Binance")]

    platform = forms.ChoiceField(choices=CHOICES)
    api_key = forms.CharField(widget=forms.PasswordInput, min_length=64, max_length=64, required=True, help_text=mark_safe('Provide with <b>READ ONLY</b> API key - <a href="https://vimeo.com/524179256">See tutorial </a>'))
    api_secret = forms.CharField(widget=forms.PasswordInput, min_length=64, max_length=64, required=True, help_text=mark_safe('Provide with <b>READ ONLY</b> API secret - <a href="https://vimeo.com/524179256">See tutorial </a>'))

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(AddTradingAccountForm, self).__init__(*args, **kwargs)
    class Meta:
        model = TradingAccount
        fields = (
            'platform',
            'api_key',
            'api_secret'
        )
    
    def clean(self):
        api_key = self.cleaned_data.get('api_key', '')
        api_secret = self.cleaned_data.get('api_secret', '')
        platform = self.cleaned_data.get('platform', '')

        if api_key and TradingAccount.objects.filter(platform__iexact=platform).filter(api_key__iexact=api_key).exists():
            raise forms.ValidationError(u'This trading account is already linked to a user.')
        
        # check if api key, secret pair is valid 
        ta = TradingAccount(user=self.user, platform=platform, api_key=api_key, api_secret=api_secret)
        tc = TradingClient.trading_from(ta)
        try:
            tc.get_balances()
        except:
            raise forms.ValidationError(u'Invalid api key, api secret pair. Please verify again.')
        return self.cleaned_data

    def save(self, commit=True):
        ta = TradingAccount(user=self.user, 
                            platform=self.cleaned_data['platform'],
                            api_key=self.cleaned_data['api_key'],
                            api_secret=self.cleaned_data['api_secret'])
        if commit:
            ta.save()
        return ta

    
class ProfileFilterForm(forms.Form):
    '''Form to validate profile filtering'''
    date_from = forms.DateField()
    date_to = forms.DateField()

    def clean(self):
        date_from = self.cleaned_data.get('date_from', '')
        date_to = self.cleaned_data.get('date_to', '')
        try:
            date_from = datetime.combine(date_from, datetime.min.time(), timezone.utc)
            date_to = datetime.combine(date_to, datetime.min.time(), timezone.utc)
        except Exception as e:
            raise forms.ValidationError(u'Unvalid date format.')

        if date_from >= date_to:
            raise forms.ValidationError(u'<Date to> must be after <Date from>.')
        
        self.cleaned_data['date_from'] = date_from
        self.cleaned_data['date_to'] = date_to
        return self.cleaned_data
        