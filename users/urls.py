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
    # User management
    path('users/', views.user_management, name='user_management'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('dismiss-alert/<str:student_id>/', views.dismiss_alert, name='dismiss_alert'),
    path('dismiss-all-alerts/', views.dismiss_all_alerts, name='dismiss_all_alerts'),
    path('reset-system/', views.reset_system_data, name='reset_system_data'),
    path('change-password/', views.change_password_request, name='change_password'),
    path('change-password/verify/', views.change_password_verify, name='change_password_verify'),
]
