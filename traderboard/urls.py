from re import template
from django.contrib import auth
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),

    path('accounts/register/', views.register, name='register'),
    path('accounts/profile/', views.show_profile, name='profile'),
    path('accounts/profile/<int:pk>/', views.show_overview_profile, name='profile_with_pk'),
    path('accounts/settings', views.show_settings, name='settings'),
    path('accounts/edit-profile/', views.edit_profile, name='edit_profile'),
    path('accounts/edit-password/', views.edit_password, name='edit_password'),
    path('accounts/trading-accounts/', views.show_trading_accounts, name='trading_accounts'),
    path('accounts/add-trading-account/', views.add_trading_account, name='add_trading_account'),
    path('accounts/remove-trading-account/<int:pk>/', views.remove_trading_account, name='remove_trading_account'),
    path('accounts/edit-settings', views.edit_settings, name='edit_settings'),

    path('accounts/login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(template_name='index.html'), name='logout'),

    path('accounts/password-reset/', 
        auth_views.PasswordResetView.as_view(template_name='accounts/password_reset_form.html',
                                            success_url='done',
                                            subject_template_name='accounts/password_reset_subject.txt',
                                            email_template_name='accounts/password_reset_email.html'
                                            ), name='password_reset'),
    path('accounts/password-reset/done/', 
        auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('accounts/password-reset/confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'), name='password_reset_confirm'),
    path('accounts/password-reset/complete/', 
        auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), name='password_reset_complete')
    ]