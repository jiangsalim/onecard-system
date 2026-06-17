from django.urls import path
from . import views

urlpatterns = [
    path('manage/', views.fee_management, name='fee_management'),
    path('report/', views.fee_report, name='fee_report'),
    path('meal-rules/', views.meal_access_rules, name='meal_access_rules'),
    path('meal-times/', views.meal_time_settings, name='meal_time_settings'),
    path('meal-violations/', views.meal_violations, name='meal_violations'),
    path('resolve-violation/<int:violation_id>/', views.resolve_violation, name='resolve_violation'),
    path('resolve-all-violations/', views.resolve_all_violations, name='resolve_all_violations'),
]