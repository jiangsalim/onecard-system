from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.core.management import call_command

handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
handler403 = 'core.views.error_403'

def trigger_daily_reports(request):
    """Trigger daily email reports for all staff."""
    try:
        call_command('send_daily_reports')
        return HttpResponse('Daily reports sent successfully!')
    except Exception as e:
        return HttpResponse(f'Error: {e}', status=500)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    path('', include('core.urls')),
    path('cards/', include('cards.urls')),
    path('movement/', include('movement.urls')),
    path('fees/', include('fees.urls')),
    path('notifications/', include('notifications.urls')),
    path('reports/', include('reports.urls')),
    path('messaging/', include('messaging.urls')),
    path('send-daily-reports/', trigger_daily_reports, name='send_daily_reports'),
    path('accounts/', include('allauth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)