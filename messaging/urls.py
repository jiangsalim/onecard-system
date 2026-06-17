from django.urls import path
from . import views

urlpatterns = [
    path('inbox/', views.inbox, name='inbox'),
    path('chat/<int:conversation_id>/', views.chat_view, name='chat'),
    path('chat/<int:conversation_id>/send/', views.send_message, name='send_message'),
    path('chat/<int:conversation_id>/new/', views.get_new_messages, name='get_new_messages'),
    path('new/', views.start_conversation, name='start_conversation'),
    path('unread/', views.unread_count, name='unread_count'),
]