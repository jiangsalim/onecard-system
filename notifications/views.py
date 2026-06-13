from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Notification, NotificationSetting
from datetime import date, timedelta, datetime
from core.mobile_utils import render_mobile_or_desktop


@login_required
def notification_list(request):
    """View all notifications."""
    notifications = Notification.objects.all().order_by('-created_at')[:50]
    unread_count = Notification.objects.filter(is_read=False).count()
    return render_mobile_or_desktop(request, 'notifications/list.html', 'mobile/notifications_list.html', {
        'notifications': notifications, 'unread_count': unread_count,
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
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    settings, _ = NotificationSetting.objects.get_or_create(id=1)
    
    if request.method == 'POST':
        settings.fee_balance_threshold = request.POST.get('fee_balance_threshold', 500000)
        settings.attendance_consecutive_days = request.POST.get('attendance_consecutive_days', 3)
        settings.movement_hours_outside = request.POST.get('movement_hours_outside', 3)
        settings.show_in_dashboard = request.POST.get('show_in_dashboard') == 'on'
        settings.save()
        messages.success(request, 'Notification settings updated!')
        return redirect('notification_settings')
    
    return render_mobile_or_desktop(request, 'notifications/settings.html', 'mobile/notifications_settings.html', {'settings': settings})


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


def auto_check_alerts():
    """Check for alert conditions and create notifications."""
    from core.models import Student
    from core.services import get_payment_balance
    from attendance.models import Attendance
    from movement.models import MovementLog

    settings = NotificationSetting.objects.first()
    if not settings:
        return 0

    today = date.today()
    alerts_created = 0

    if settings.fee_balance_threshold:
        for s in Student.objects.filter(status='active')[:100]:
            paid = get_payment_balance(s.payment_code)
            if float(paid) >= float(settings.fee_balance_threshold):
                continue
            already_notified = Notification.objects.filter(related_student=s, category='fee', created_at__date=today).exists()
            if not already_notified:
                Notification.objects.create(
                    title='Fee Balance Alert',
                    message=f'Student {s.id} ({s.admission_number}) has a balance above threshold.',
                    priority='medium', category='fee', related_student=s,
                )
                alerts_created += 1

    if settings.attendance_consecutive_days:
        cutoff = today - timedelta(days=settings.attendance_consecutive_days)
        absent_students = Student.objects.filter(status='active').exclude(attendance_records__scan_date__gte=cutoff)[:50]
        for s in absent_students:
            already_notified = Notification.objects.filter(related_student=s, category='attendance', created_at__date=today).exists()
            if not already_notified:
                Notification.objects.create(
                    title='Absent Alert',
                    message=f'Student {s.id} ({s.admission_number}) absent for {settings.attendance_consecutive_days}+ consecutive days.',
                    priority='high', category='attendance', related_student=s,
                )
                alerts_created += 1

    if settings.movement_hours_outside:
        hours_ago = (datetime.now() - timedelta(hours=int(settings.movement_hours_outside))).time()
        long_out = MovementLog.objects.filter(exit_date=today, time_in__isnull=True, time_out__lte=hours_ago)[:50]
        for m in long_out:
            already_notified = Notification.objects.filter(related_student=m.student, category='movement', created_at__date=today).exists()
            if not already_notified:
                Notification.objects.create(
                    title='Student Outside Too Long',
                    message=f'Student {m.student.id} has been outside since {m.time_out} ({settings.movement_hours_outside}+ hours).',
                    priority='high', category='movement', related_student=m.student,
                )
                alerts_created += 1

    return alerts_created