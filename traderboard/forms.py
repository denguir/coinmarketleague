from sys import platform
from django import forms
from django.contrib.auth.models import User
from django.forms.widgets import RadioSelect
from traderboard.models import Profile, TradingAccount
from TradingClient import TradingClient
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django_toggle_switch_widget.widgets import DjangoToggleSwitchWidget


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
    username = forms.CharField(max_length=30, disabled=True)
    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
        )


class EditSettingsForm(forms.ModelForm):
    public = forms.BooleanField(help_text='Put your account on public mode.\
                                        It implies that other people can see your balance information.')
    class Meta:
        model = Profile
        fields = ('public', )


class AddTradingAccountForm(forms.ModelForm):
    '''Form to link a trading account to your profile'''

    CHOICES = [("Binance", "Binance")]

    platform = forms.ChoiceField(choices=CHOICES)
    api_key = forms.CharField(widget=forms.PasswordInput, min_length=64, max_length=64, required=True, help_text='Provide with READ ONLY API key')
    api_secret = forms.CharField(widget=forms.PasswordInput, min_length=64, max_length=64, required=True, help_text='Provide with READ ONLY API secret')

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
        api_key = self.cleaned_data['api_key']
        api_secret = self.cleaned_data['api_secret']
        platform = self.cleaned_data['platform']

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


