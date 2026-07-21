from django.urls import path
from . import views
from . import api_views
urlpatterns = [
    path('import-students/', views.import_students, name='import_students'),
    path('view-students/', views.view_students, name='view_students'),
    path('edit-student/<str:student_id>/', views.edit_student, name='edit_student'),
    path('api/scan/', api_views.process_scan, name='api_scan'),
    path('api/students-list/', api_views.api_students_list, name='api_students_list'),
    path('api/import-students/', api_views.api_import_students, name='api_import_students'),
    path('api/import-progress/', api_views.api_import_progress, name='api_import_progress'),
    path('api/public/balance/', api_views.public_balance, name='public_balance'),
    path('api/public/statement/', api_views.public_statement_pdf, name='public_statement'),
    path('api/public/balance-by-card/', api_views.public_balance_by_card, name='public_balance_by_card'),
    path('api/public/statement-by-card/', api_views.public_statement_by_card_pdf, name='public_statement_by_card'),
    path('backup/', views.backup_now, name='backup_now'),
]
