from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core.models import Student
from .models import MovementLog
from datetime import date, datetime
import json
import logging

logger = logging.getLogger('onecard')


@login_required
def movement_dashboard(request):
    today = date.today()
    active_passes = MovementLog.objects.filter(exit_date=today, time_in__isnull=True).select_related('student')
    today_logs = MovementLog.objects.filter(exit_date=today).select_related('student').order_by('-time_out')[:20]
    return render(request, 'movement/dashboard.html', {'active_passes': active_passes, 'today_logs': today_logs})


@login_required
@require_POST
def process_pass_out(request):
    """Confirm a pass-out exit."""
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
        
        # Check if already outside
        existing = MovementLog.objects.filter(student=student, exit_date=today, time_in__isnull=True).first()
        if existing:
            return JsonResponse({'success': False, 'error': 'Student is already outside.'})
        
        # Create exit record
        MovementLog.objects.create(
            student=student, exit_date=today, time_out=now,
            reason=reason, authorized_by=authorized_by
        )
        
        return JsonResponse({'success': True, 'message': 'Exit logged successfully.'})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        logger.error(f"Pass-out error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
def movement_history(request):
    logs = MovementLog.objects.select_related('student').all().order_by('-exit_date', '-time_out')[:100]
    return render(request, 'movement/history.html', {'logs': logs})