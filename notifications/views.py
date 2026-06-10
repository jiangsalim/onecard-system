from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Notification, NotificationSetting


@login_required
def notification_list(request):
    """View all notifications."""
    notifications = Notification.objects.all().order_by('-created_at')[:50]
    unread_count = Notification.objects.filter(is_read=False).count()
    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def mark_as_read(request, notification_id):
    """Mark a notification as read."""
    try:
        notif = Notification.objects.get(id=notification_id)
        notif.is_read = True
        notif.save()
    except Notification.DoesNotExist:
        pass
    return redirect('notification_list')


@login_required
def mark_all_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(is_read=False).update(is_read=True)
    return redirect('notification_list')


@login_required
def notification_settings(request):
    """Manage notification settings."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    settings, _ = NotificationSetting.objects.get_or_create(id=1)
    
    if request.method == 'POST':
        settings.fee_balance_threshold = request.POST.get('fee_balance_threshold', 500000)
        settings.attendance_consecutive_days = request.POST.get('attendance_consecutive_days', 3)
        settings.movement_hours_outside = request.POST.get('movement_hours_outside', 3)
        settings.show_in_dashboard = request.POST.get('show_in_dashboard') == 'on'
        settings.save()
        messages.success(request, 'Notification settings updated!')
        return redirect('notification_settings')
    
    return render(request, 'notifications/settings.html', {'settings': settings})


@login_required
def create_test_notification(request):
    """Create a test notification."""
    Notification.objects.create(
        title='Test Notification',
        message='This is a test notification from the OneCard system.',
        priority='medium',
        category='system'
    )
    messages.success(request, 'Test notification created!')
    return redirect('notification_list')