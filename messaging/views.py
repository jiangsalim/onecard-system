from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Conversation, Message
from users.models import User
from core.mobile_utils import render_mobile_or_desktop


@login_required
def inbox(request):
    """List all conversations for the current user."""
    conversations = request.user.conversations.all()
    
    # Add unread count to each conversation
    for conv in conversations:
        conv.unread = conv.unread_count(request.user)
        conv.last_msg = conv.last_message()
    
    # Total unread across all conversations
    total_unread = sum(conv.unread for conv in conversations)
    
    return render_mobile_or_desktop(request, 'messaging/inbox.html', 'mobile/messaging_inbox.html', {
        'conversations': conversations,
        'total_unread': total_unread,
    })


@login_required
def chat_view(request, conversation_id):
    """View a specific conversation."""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Security: only participants can view
    if request.user not in conversation.participants.all():
        messages.error(request, 'Access denied.')
        return redirect('inbox')
    
    # Mark messages as read
    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    
    # Get other participant info
    other_user = conversation.participants.exclude(id=request.user.id).first()
    
    return render_mobile_or_desktop(request, 'messaging/chat.html', 'mobile/messaging_chat.html', {
        'conversation': conversation,
        'messages': conversation.messages.all(),
        'other_user': other_user,
    })


@login_required
def start_conversation(request):
    """Start a new conversation or find existing one."""
    if request.method == 'POST':
        other_user_id = request.POST.get('user_id')
        other_user = get_object_or_404(User, id=other_user_id)
        
        # Check if conversation already exists
        existing = Conversation.objects.filter(
            participants=request.user
        ).filter(
            participants=other_user
        ).first()
        
        if existing:
            return redirect('chat', conversation_id=existing.id)
        
        # Create new conversation
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)
        
        return redirect('chat', conversation_id=conversation.id)
    
    # GET: Show user list (exclude self)
    users = User.objects.filter(is_active=True).exclude(id=request.user.id).order_by('role', 'username')
    return render_mobile_or_desktop(request, 'messaging/new_chat.html', 'mobile/messaging_new_chat.html', {
        'users': users,
    })


@login_required
def send_message(request, conversation_id):
    """Send a message via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    if request.user not in conversation.participants.all():
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'success': False, 'error': 'Empty message'})
    
    msg = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        content=content,
    )
    
    return JsonResponse({
        'success': True,
        'message': {
            'id': msg.id,
            'content': msg.content,
            'sender': msg.sender.get_full_name() or msg.sender.username,
            'is_me': True,
            'time': msg.created_at.strftime('%H:%M'),
        }
    })


@login_required
def get_new_messages(request, conversation_id):
    """Get new messages since last check (polling)."""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    if request.user not in conversation.participants.all():
        return JsonResponse({'success': False})
    
    last_id = request.GET.get('last_id', 0)
    new_messages = conversation.messages.filter(id__gt=last_id).exclude(sender=request.user)
    
    # Mark as read
    new_messages.update(is_read=True)
    
    return JsonResponse({
        'success': True,
        'messages': [{
            'id': m.id,
            'content': m.content,
            'sender': m.sender.get_full_name() or m.sender.username,
            'time': m.created_at.strftime('%H:%M'),
        } for m in new_messages]
    })


@login_required
def unread_count(request):
    """Get total unread message count (for badge)."""
    count = Message.objects.filter(
        conversation__participants=request.user,
        is_read=False,
    ).exclude(sender=request.user).count()
    
    return JsonResponse({'count': count})