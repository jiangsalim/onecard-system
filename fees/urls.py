from django.urls import path
from . import views

urlpatterns = [
    path('manage/', views.fee_management, name='fee_management'),
    path('report/', views.fee_report, name='fee_report'),
    path('meal-rules/', views.meal_access_rules, name='meal_access_rules'),
]