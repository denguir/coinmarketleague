from django.urls import path, include
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.show_profile, name='profile'),
    path('profile/<int:pk>/', views.show_overview_profile, name='profile_with_pk'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    ]