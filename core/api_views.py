from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Student
from .services import get_student_info_from_existing_db, get_payment_balance
from attendance.models import Attendance
from fees.models import FeeStructure
from datetime import date, datetime
import json
import logging

logger = logging.getLogger('onecard')


@login_required
@require_POST
def process_scan(request):
    """Process a QR code scan."""
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        location = data.get('location', 'Main Gate')
        mode = data.get('mode', 'attendance_balance')
        
        if not student_id:
            return JsonResponse({'success': False, 'error': 'No student ID provided'}, status=400)
        
        # Get student from OneCard DB
        try:
            student = Student.objects.select_related('template').get(id=student_id, status='active')
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Student not found or inactive'})
        
        # Check if this is an old card (replaced by reprint)
        if student.reprint_count > 0 and student.last_reprint_date:
            return JsonResponse({
                'success': False,
                'error': f'CARD REPLACED — This card was replaced on {student.last_reprint_date}. Reprint #{student.reprint_count} is active.',
                'error_code': 'CARD_REPLACED',
                'reprint_count': student.reprint_count,
            }, status=410)
        
        # Get student info from existing school DB
        info = get_student_info_from_existing_db(student.admission_number)
        if not info:
            return JsonResponse({
                'success': False,
                'error': 'Cannot fetch student data. School database may be unavailable.',
                'error_code': 'DB_UNAVAILABLE',
            }, status=503)
        
        # Get balance
        total_paid = get_payment_balance(student.payment_code)
        fee = FeeStructure.objects.filter(class_name=info['class']).first()
        
        if not fee:
            return JsonResponse({
                'success': False,
                'error': f'Fee structure not set for {info["class"]}. Contact admin.',
                'error_code': 'NO_FEE_STRUCTURE',
            }, status=400)
        
        total_fees = float(fee.total_fees)
        balance = total_fees - float(total_paid)
        
        if balance <= 0 and float(total_paid) > 0:
            status = 'CLEARED'
        elif float(total_paid) > total_fees:
            status = 'OVERPAID'
        elif float(total_paid) == 0:
            status = 'NOT PAID'
        else:
            status = 'NOT CLEARED'
        
        # Log attendance if in attendance mode
        already_marked = False
        if mode == 'attendance_balance':
            today = date.today()
            already_marked = Attendance.objects.filter(student=student, scan_date=today).exists()
            if not already_marked:
                Attendance.objects.create(
                    student=student,
                    scan_date=today,
                    time_in=datetime.now().time(),
                    scan_location=location,
                    marked_by=request.user.get_full_name() or request.user.username
                )
        
        return JsonResponse({
            'success': True,
            'student': {
                'id': student.id,
                'name': info['name'],
                'class': info['class'],
                'stream': info['stream'],
                'admission': student.admission_number,
                'payment_code': student.payment_code,
            },
            'fees': {
                'total': total_fees,
                'paid': float(total_paid),
                'balance': balance,
                'status': status,
            },
            'attendance': {
                'marked': not already_marked,
                'already_marked': already_marked,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        logger.error(f"Scan error: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)