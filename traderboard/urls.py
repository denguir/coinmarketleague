from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='index.html'), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.show_profile, name='profile'),
    path('profile/<int:pk>/', views.show_overview_profile, name='profile_with_pk'),
    path('settings', views.show_settings, name='settings'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('edit-password/', views.edit_password, name='edit_password'),
    
    ]