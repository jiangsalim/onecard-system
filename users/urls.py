from django.urls import path
from . import views

urlpatterns = [
    path('', views.redirect_to_login, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('bursar-dashboard/', views.bursar_dashboard, name='bursar_dashboard'),
    path('gate-dashboard/', views.gate_dashboard, name='gate_dashboard'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('scanner/', views.scanner_view, name='scanner'),
]