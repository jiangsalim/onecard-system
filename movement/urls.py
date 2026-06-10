from django.urls import path
from . import views

urlpatterns = [
    path('', views.movement_dashboard, name='movement_dashboard'),
    path('api/pass-out/', views.process_pass_out, name='api_pass_out'),
    path('history/', views.movement_history, name='movement_history'),
]