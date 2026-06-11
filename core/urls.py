from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    path('import-students/', views.import_students, name='import_students'),
    path('view-students/', views.view_students, name='view_students'),
    path('api/scan/', api_views.process_scan, name='api_scan'),
    path('test-404/', views.error_404, name='test_404'),
    path('test-500/', views.error_500, name='test_500'),
    path('backup/', views.backup_now, name='backup_now'),
]