from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    path('import-students/', views.import_students, name='import_students'),
    path('view-students/', views.view_students, name='view_students'),
    path('api/scan/', api_views.process_scan, name='api_scan'),
]