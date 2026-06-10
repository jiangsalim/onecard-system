from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    path('', include('core.urls')),
    path('cards/', include('cards.urls')),
    path('movement/', include('movement.urls')),
]