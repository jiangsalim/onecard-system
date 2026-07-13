from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

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
    path('send-daily-reports/', lambda r: __import__('django.core.management').management.call_command('send_daily_reports') or __import__('django.http').HttpResponse('OK')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)