from django.urls import path
from . import views

urlpatterns = [
    path('attendance/', views.attendance_report, name='attendance_report'),
    path('export/attendance/', views.export_attendance, name='export_attendance'),
    path('export/fees/', views.export_fees, name='export_fees'),
    path('export/movement/', views.export_movement, name='export_movement'),
]