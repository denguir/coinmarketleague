from django import forms
from django.contrib.auth.models import User
from traderboard.models import TradingAccount
from TradingClient import TradingClient
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

__PLATFORMS__ = ['Binance']

class RegistrationForm(UserCreationForm):
    # username = forms.CharField(max_length=30, required=True)
    # first_name = forms.CharField(max_length=30, required=False, help_text='Optional')
    # last_name = forms.CharField(max_length=30, required=False, help_text='Optional')
    email = forms.EmailField(max_length=254, required=True, help_text='Enter a valid email address')

    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'password1',
            'password2'
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

    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'password'
        )


class AddTradingAccountForm(forms.ModelForm):

    platform = forms.ChoiceField(choices=list(enumerate(__PLATFORMS__)))
    api_key = forms.CharField(min_length=64, max_length=64, required=True, help_text='Provide with READ ONLY API key')
    api_secret = forms.CharField(min_length=64, max_length=64, required=True, help_text='Provide with READ ONLY API secret')

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
    
    def clean_api_key(self):
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
        return api_key

