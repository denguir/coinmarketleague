from django import forms
from django.contrib.auth.models import User
from django.forms import fields
from models import TradingAccount
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

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
    api_key = forms.CharField(max_length=64, required=True, help_text='Provide with READ ONLY API key')
    api_secret = forms.CharField(max_length=64, required=True, help_text='Provide with READ ONLY API secret')

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
        # TODO:
        # verify if api_key, api_secret pair is not already present in database using SearchField
        # try to log on with api client and see if no errors 