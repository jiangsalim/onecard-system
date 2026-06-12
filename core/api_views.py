from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Student
from .services import get_student_info_from_existing_db, get_payment_balance, fetch_students_from_existing_db, generate_qr_for_student, get_next_student_id
from attendance.models import Attendance
from movement.models import MovementLog
from fees.models import FeeStructure
from datetime import date, datetime
import json
import logging
from datetime import time

logger = logging.getLogger('onecard')


@login_required
@require_POST
def process_scan(request):
    """Process a QR code scan — attendance, balance, or pass-out."""
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        location = data.get('location', 'Main Gate')
        mode = data.get('mode', 'attendance_balance')
        
        if not student_id:
            return JsonResponse({'success': False, 'error': 'No student ID provided'}, status=400)
        
        # Parse QR data: "STU-001:v1" or just "STU-001"
        qr_version = 1
        if ':v' in student_id:
            parts = student_id.split(':v')
            student_id = parts[0]
            try: qr_version = int(parts[1])
            except (ValueError, IndexError): qr_version = 1
        
        # Get student from OneCard DB
        try:
            student = Student.objects.select_related('template').get(id=student_id, status='active')
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Student not found or inactive'})
        
        # Check card version
        if qr_version < student.card_version:
            return JsonResponse({
                'success': False,
                'error': f'CARD REPLACED — This card (v{qr_version}) was replaced on {student.last_reprint_date}. Current card is v{student.card_version}.',
                'error_code': 'CARD_REPLACED',
            }, status=410)
        
        # Get student info from school DB
        info = get_student_info_from_existing_db(student.admission_number)
        if not info:
            return JsonResponse({'success': False, 'error': 'Cannot fetch student data.', 'error_code': 'DB_UNAVAILABLE'}, status=503)
        
        # ========== PASS OUT MODE ==========
        if mode == 'pass_out':
            today = date.today()
            existing = MovementLog.objects.filter(student=student, exit_date=today, time_in__isnull=True).first()
            
            if existing:
                # Student is returning
                now_time = datetime.now().time()
                existing.time_in = now_time
                existing.save()
                
                # Calculate duration
                out_dt = datetime.combine(today, existing.time_out)
                in_dt = datetime.combine(today, now_time)
                diff = in_dt - out_dt
                hours = diff.seconds // 3600
                minutes = (diff.seconds % 3600) // 60
                
                return JsonResponse({
                    'success': True,
                    'student': {
                        'id': student.id, 'name': info['name'],
                        'class': info['class'], 'stream': info['stream'],
                        'admission': student.admission_number,
                    },
                    'movement': {
                        'action': 'return',
                        'time_out': str(existing.time_out),
                        'time_in': str(now_time),
                        'duration': f'{hours}h {minutes}m',
                    }
                })
            else:
                # Student is leaving — show exit form
                return JsonResponse({
                    'success': True,
                    'student': {
                        'id': student.id, 'name': info['name'],
                        'class': info['class'], 'stream': info['stream'],
                        'admission': student.admission_number,
                    },
                    'movement': {
                        'action': 'exit',
                    }
                })
            
                # ========== MEAL TRACKING MODE ==========
        if mode == 'meal_tracking':
            from attendance.models import MealLog
            
            # Determine meal type from current time
            now = datetime.now().time()
            if time(7, 0) <= now <= time(8, 30):
                meal_type = 'breakfast'
            elif time(12, 30) <= now <= time(14, 0):
                meal_type = 'lunch'
            elif time(18, 0) <= now <= time(19, 30):
                meal_type = 'supper'
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Not meal time. Meals: Breakfast 7-8:30, Lunch 12:30-14:00, Supper 18:00-19:30',
                    'error_code': 'NOT_MEAL_TIME'
                })
            
            # Get student category
            student_category = student.category if hasattr(student, 'category') else 'day'
            
            # Check meal eligibility
            if student_category == 'day' and meal_type != 'lunch':
                return JsonResponse({
                    'success': False,
                    'error': f'DAY SCHOLAR — {meal_type.title()} is not available for day students. Only Lunch.',
                    'error_code': 'MEAL_NOT_ALLOWED',
                    'category': student_category,
                    'meal_type': meal_type
                })
            
            # Check if already eaten this meal
            today = date.today()
            already_eaten = MealLog.objects.filter(
                student=student, meal_date=today, meal_type=meal_type
            ).first()
            
            if already_eaten:
                return JsonResponse({
                    'success': False,
                    'error': f'ALREADY SERVED — {meal_type.title()} at {already_eaten.time_scanned}',
                    'error_code': 'ALREADY_SERVED',
                    'meal_type': meal_type,
                    'time_scanned': str(already_eaten.time_scanned)
                })
            
            # Mark meal
            MealLog.objects.create(
                student=student,
                meal_date=today,
                meal_type=meal_type,
                time_scanned=now,
                location=location,
                marked_by=request.user.get_full_name() or request.user.username
            )
            
            return JsonResponse({
                'success': True,
                'meal': {
                    'type': meal_type,
                    'category': student_category,
                    'time': str(now),
                },
                'student': {
                    'id': student.id,
                    'name': info['name'],
                    'class': info['class'],
                    'stream': info['stream'],
                }
            })
        
        # ========== ATTENDANCE / BALANCE MODE ==========
        total_paid = get_payment_balance(student.payment_code)
        student_category = student.category if hasattr(student, 'category') else 'day'
        fee = FeeStructure.objects.filter(class_name=info['class'], category=student_category).first()
        
        if not fee:
            return JsonResponse({'success': False, 'error': f'Fee structure not set for {info["class"]}.', 'error_code': 'NO_FEE_STRUCTURE'}, status=400)
        
        total_fees = float(fee.total_fees)
        balance = total_fees - float(total_paid)
        
        if balance <= 0 and float(total_paid) > 0: status = 'CLEARED'
        elif float(total_paid) > total_fees: status = 'OVERPAID'
        elif float(total_paid) == 0: status = 'NOT PAID'
        else: status = 'NOT CLEARED'
        
        already_marked = False
        if mode == 'attendance_balance':
            today = date.today()
            already_marked = Attendance.objects.filter(student=student, scan_date=today).exists()
            if not already_marked:
                Attendance.objects.create(student=student, scan_date=today, time_in=datetime.now().time(), scan_location=location, marked_by=request.user.get_full_name() or request.user.username)
        
        return JsonResponse({
            'success': True,
            'student': {'id': student.id, 'name': info['name'], 'class': info['class'], 'stream': info['stream'], 'admission': student.admission_number, 'payment_code': student.payment_code},
            'fees': {'total': total_fees, 'paid': float(total_paid), 'balance': balance, 'status': status},
            'attendance': {'marked': not already_marked, 'already_marked': already_marked}
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        logger.error(f"Scan error: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

@login_required
def api_students_list(request):
    """Paginated student list from school DB — excludes already imported."""
    students = fetch_students_from_existing_db()
    imported_ids = set(Student.objects.values_list('admission_number', flat=True))
    students = [s for s in students if s['admission_number'] not in imported_ids]
    
    cls = request.GET.get('cls', '')
    stream = request.GET.get('stream', '')
    search = request.GET.get('search', '').lower()
    
    if cls:
        students = [s for s in students if s['current_class'] == cls]
    if stream:
        students = [s for s in students if s['stream'] == stream]
    if search:
        students = [s for s in students if search in s['full_name'].lower() or search in s['admission_number'].lower()]
    
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 50))
    total = len(students)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    
    return JsonResponse({
        'students': students[start:end],
        'total': total, 'page': page, 'total_pages': total_pages,
        'imported_count': len(imported_ids), 'remaining_count': total,
    })


@login_required
@require_POST
def api_import_students(request):
    """Import selected students via AJAX - optimized with batch processing."""
    try:
        data = json.loads(request.body)
        selected = data.get('students', [])
        import_all = data.get('import_all', False)
        
        # If import_all is True, fetch ALL unimported students from school DB
        if import_all:
            all_school = fetch_students_from_existing_db()
            imported_ids = set(Student.objects.values_list('admission_number', flat=True))
            selected = [s['admission_number'] for s in all_school if s['admission_number'] not in imported_ids]
        
        if not selected:
            return JsonResponse({'success': False, 'message': 'No students to import.'})
        
        # Fetch ALL school students ONCE
        all_school_students = fetch_students_from_existing_db()
        school_dict = {s['admission_number']: s for s in all_school_students}
        
        imported = 0
        skipped = 0
        errors = 0
        
        for admission_number in selected:
            try:
                if Student.objects.filter(admission_number=admission_number).exists():
                    skipped += 1
                    continue
                
                student_data = school_dict.get(admission_number)
                if not student_data:
                    errors += 1
                    continue
                
                student_id = get_next_student_id()
                qr_file = generate_qr_for_student(student_id)
                
                student = Student(
                    id=student_id,
                    admission_number=admission_number,
                    payment_code=student_data['payment_code'],
                    category=student_data.get('category', 'day'),
                    status='active',
                    card_version=1
                )
                student.qr_code.save(f'{student_id}.png', qr_file, save=False)
                student.save()
                imported += 1
                
            except Exception as e:
                logger.error(f"Import error for {admission_number}: {e}")
                errors += 1
        
        message = f'Imported: {imported}'
        if skipped > 0: message += f' | Skipped: {skipped}'
        if errors > 0: message += f' | Errors: {errors}'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'imported': Student.objects.filter(status='active').count(),
        })
        
    except Exception as e:
        logger.error(f"Import batch error: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)})