from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core.models import Student
from .models import MovementLog
from datetime import date, datetime
from core.mobile_utils import render_mobile_or_desktop
import json
import logging

logger = logging.getLogger('onecard')


def get_class_student_ids(class_filter, stream_filter):
    """Helper to get student IDs for a class/stream."""
    if not class_filter:
        return None
    from core.services import fetch_students_from_existing_db
    all_school = fetch_students_from_existing_db()
    matching = [
        s['admission_number'] for s in all_school 
        if s['current_class'] == class_filter 
        and (not stream_filter or s['stream'] == stream_filter)
    ]
    return Student.objects.filter(admission_number__in=matching, status='active').values_list('id', flat=True)


@login_required
def movement_dashboard(request):
    today = date.today()
    
    class_filter = request.GET.get('class', '')
    stream_filter = request.GET.get('stream', '')
    if request.user.role == 'class_teacher':
        class_filter = request.user.assigned_class
        stream_filter = request.user.assigned_stream
    
    student_ids = get_class_student_ids(class_filter, stream_filter)
    
    if student_ids is not None:
        active_passes = MovementLog.objects.filter(exit_date=today, time_in__isnull=True, student_id__in=student_ids).select_related('student')
        today_logs = MovementLog.objects.filter(exit_date=today, student_id__in=student_ids).select_related('student').order_by('-time_out')[:20]
    else:
        active_passes = MovementLog.objects.filter(exit_date=today, time_in__isnull=True).select_related('student')
        today_logs = MovementLog.objects.filter(exit_date=today).select_related('student').order_by('-time_out')[:20]
    
    return render_mobile_or_desktop(request, 'movement/dashboard.html', 'mobile/movement_dashboard.html', {
        'active_passes': active_passes, 'today_logs': today_logs,
    })


@login_required
@require_POST
def process_pass_out(request):
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        reason = data.get('reason', 'other')
        authorized_by = data.get('authorized_by', request.user.get_full_name() or request.user.username)
        location = data.get('location', 'Main Gate')
        
        if not student_id:
            return JsonResponse({'success': False, 'error': 'No student ID'}, status=400)
        
        try:
            student = Student.objects.get(id=student_id, status='active')
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Student not found'})
        
        today = date.today()
        now = datetime.now().time()
        
        existing = MovementLog.objects.filter(student=student, exit_date=today, time_in__isnull=True).first()
        if existing:
            return JsonResponse({'success': False, 'error': 'Student is already outside.'})
        
        MovementLog.objects.create(student=student, exit_date=today, time_out=now, reason=reason, authorized_by=authorized_by)
        return JsonResponse({'success': True, 'message': 'Exit logged successfully.'})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        logger.error(f"Pass-out error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
def movement_history(request):
    class_filter = request.GET.get('class', '')
    stream_filter = request.GET.get('stream', '')
    if request.user.role == 'class_teacher':
        class_filter = request.user.assigned_class
        stream_filter = request.user.assigned_stream
    
    student_ids = get_class_student_ids(class_filter, stream_filter)
    
    if student_ids is not None:
        logs = MovementLog.objects.filter(student_id__in=student_ids).select_related('student').order_by('-exit_date', '-time_out')[:100]
    else:
        logs = MovementLog.objects.select_related('student').all().order_by('-exit_date', '-time_out')[:100]
    
    return render_mobile_or_desktop(request, 'movement/history.html', 'mobile/movement_history.html', {'logs': logs})