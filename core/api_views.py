from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .models import Student, APIClient
from .services import get_student_info_from_existing_db, get_payment_balance, fetch_students_from_existing_db, generate_qr_for_student, get_next_student_id
from attendance.models import Attendance, MealLog, MealAccessRule, MealTimeSettings, MealViolation
from movement.models import MovementLog
from fees.models import FeeStructure
from datetime import date, datetime, time
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import json
import logging

logger = logging.getLogger('onecard')


def build_photo_url(request, photo_path):
    """Convert a photo path to a full URL, or return empty string."""
    if not photo_path:
        return ''
    return request.build_absolute_uri(settings.MEDIA_URL + photo_path)


# ============================================================
# PUBLIC API (No login required — API key + IP + rate limit)
# ============================================================

@csrf_exempt
def public_balance(request):
    """Public API: Check student balance by payment code. Requires API key in header."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'GET required'}, status=405)
    
    # Validate API key from header
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API key required'}, status=401)
    
    try:
        client = APIClient.objects.get(api_key=api_key, is_active=True)
    except APIClient.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid API key'}, status=403)
    
    # IP restriction
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    if client.allowed_ip and client_ip != client.allowed_ip and client_ip != '127.0.0.1':
        return JsonResponse({'success': False, 'error': 'Access denied from this IP'}, status=403)
    
    # Rate limit: 5 requests per minute per IP
    cache_key = f'public_rate_{client_ip}'
    count = cache.get(cache_key, 0)
    if count >= 5:
        return JsonResponse({'success': False, 'error': 'Too many requests. Try again later.'}, status=429)
    cache.set(cache_key, count + 1, 60)
    
    payment_code = request.GET.get('payment_code', '').strip()
    if not payment_code:
        return JsonResponse({'success': False, 'error': 'Payment code required'}, status=400)
    
    # Look up student
    try:
        student = Student.objects.get(payment_code=payment_code, status='active')
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    
    # Get student info
    info = get_student_info_from_existing_db(student.admission_number)
    if not info:
        return JsonResponse({'success': False, 'error': 'Student data unavailable'}, status=503)
    
    # Calculate fees
    student_category = student.category if hasattr(student, 'category') else 'day'
    fee = FeeStructure.objects.filter(class_name=info['class'], category=student_category).first()
    total_fees = float(fee.total_fees) if fee else 800000
    
    total_paid = get_payment_balance(student.payment_code)
    balance = total_fees - float(total_paid)
    
    if balance <= 0 and float(total_paid) > 0:
        status_text = 'CLEARED'
    elif float(total_paid) == 0:
        status_text = 'NOT PAID'
    else:
        status_text = 'NOT CLEARED'
    
    pct = round((float(total_paid) / total_fees * 100), 1) if total_fees > 0 else 0
    
    # Get payment history
    payment_history = []
    try:
        from django.db import connections
        with connections['school_db'].cursor() as cursor:
            cursor.execute("""
                SELECT payment_date, payment_method, amount_paid, term, academic_year
                FROM payments WHERE payment_code = %s
                ORDER BY payment_date DESC LIMIT 20
            """, [student.payment_code])
            for row in cursor.fetchall():
                payment_history.append({
                    'date': str(row[0])[:10],
                    'method': row[1] or 'N/A',
                    'amount': float(row[2]),
                    'term': row[3] or '',
                    'year': row[4] or '',
                })
    except Exception:
        pass
    
    return JsonResponse({
        'success': True,
        'student': {
            'name': info['name'],
            'class': info['class'],
            'stream': info['stream'],
            'admission': student.admission_number,
            'category': student_category.title(),
        },
        'fees': {
            'total': total_fees,
            'paid': float(total_paid),
            'balance': balance,
            'status': status_text,
            'percentage': pct,
        },
        'history': payment_history,
    })

@csrf_exempt
def public_balance_by_card(request):
    """Public API: Check balance by scanning student card (student ID like STU-001)."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'GET required'}, status=405)
    
    # Validate API key
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API key required'}, status=401)
    
    try:
        client = APIClient.objects.get(api_key=api_key, is_active=True)
    except APIClient.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid API key'}, status=403)
    
    # IP restriction
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    if client.allowed_ip and client_ip != client.allowed_ip and client_ip != '127.0.0.1':
        return JsonResponse({'success': False, 'error': 'Access denied from this IP'}, status=403)
    
    # Rate limit
    cache_key = f'public_rate_{client_ip}'
    count = cache.get(cache_key, 0)
    if count >= 5:
        return JsonResponse({'success': False, 'error': 'Too many requests. Try again later.'}, status=429)
    cache.set(cache_key, count + 1, 60)
    
    student_id = request.GET.get('student_id', '').strip()
    if not student_id:
        return JsonResponse({'success': False, 'error': 'Student ID required'}, status=400)
    
    # Clean QR data: "STU-001:v1" → "STU-001"
    if ':v' in student_id:
        student_id = student_id.split(':v')[0]
    
    # Look up student by OneCard ID
    try:
        student = Student.objects.get(id=student_id, status='active')
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    
    # Get student info
    info = get_student_info_from_existing_db(student.admission_number)
    if not info:
        return JsonResponse({'success': False, 'error': 'Student data unavailable'}, status=503)
    
    # Build photo URL
    photo_path = info.get('photo', '')
    photo_url = build_photo_url(request, photo_path) if photo_path else ''
    
    # Calculate fees
    student_category = student.category if hasattr(student, 'category') else 'day'
    fee = FeeStructure.objects.filter(class_name=info['class'], category=student_category).first()
    total_fees = float(fee.total_fees) if fee else 800000
    
    total_paid = get_payment_balance(student.payment_code)
    balance = total_fees - float(total_paid)
    
    if balance <= 0 and float(total_paid) > 0:
        status_text = 'CLEARED'
    elif float(total_paid) == 0:
        status_text = 'NOT PAID'
    else:
        status_text = 'NOT CLEARED'
    
    pct = round((float(total_paid) / total_fees * 100), 1) if total_fees > 0 else 0
    
    # Payment history
    payment_history = []
    try:
        from django.db import connections
        with connections['school_db'].cursor() as cursor:
            cursor.execute("""
                SELECT payment_date, payment_method, amount_paid, term, academic_year
                FROM payments WHERE payment_code = %s
                ORDER BY payment_date DESC LIMIT 20
            """, [student.payment_code])
            for row in cursor.fetchall():
                payment_history.append({
                    'date': str(row[0])[:10],
                    'method': row[1] or 'N/A',
                    'amount': float(row[2]),
                    'term': row[3] or '',
                    'year': row[4] or '',
                })
    except Exception:
        pass
    
    return JsonResponse({
        'success': True,
        'student': {
            'name': info['name'],
            'class': info['class'],
            'stream': info['stream'],
            'admission': student.admission_number,
            'category': student_category.title(),
            'photo_url': photo_url,
        },
        'fees': {
            'total': total_fees,
            'paid': float(total_paid),
            'balance': balance,
            'status': status_text,
            'percentage': pct,
        },
        'history': payment_history,
    })


@csrf_exempt
def public_statement_pdf(request):
    """Public API: Download PDF statement. Requires API key + payment_code."""
    api_key = request.GET.get('api_key', '')
    payment_code = request.GET.get('payment_code', '').strip()
    
    if not api_key or not payment_code:
        return HttpResponse('Invalid request', status=400)
    
    try:
        APIClient.objects.get(api_key=api_key, is_active=True)
    except APIClient.DoesNotExist:
        return HttpResponse('Unauthorized', status=403)
    
    try:
        student = Student.objects.get(payment_code=payment_code, status='active')
    except Student.DoesNotExist:
        return HttpResponse('Student not found', status=404)
    
    info = get_student_info_from_existing_db(student.admission_number)
    if not info:
        return HttpResponse('Student data unavailable', status=503)
    
    total_paid = get_payment_balance(student.payment_code)
    student_category = student.category if hasattr(student, 'category') else 'day'
    fee = FeeStructure.objects.filter(class_name=info['class'], category=student_category).first()
    total_fees = float(fee.total_fees) if fee else 800000
    balance = total_fees - float(total_paid)
    
    # Build PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    
    elements.append(Paragraph("JINJA SENIOR SECONDARY SCHOOL", styles['Title']))
    elements.append(Paragraph("Fee Statement", styles['Heading2']))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"<b>Student:</b> {info['name']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Class:</b> {info['class']} {info['stream']} | <b>Category:</b> {student_category.title()}", styles['Normal']))
    elements.append(Paragraph(f"<b>Payment Code:</b> {payment_code}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date:</b> {timezone.now().strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Fee summary table
    fee_data = [
        ['Description', 'Amount (UGX)'],
        ['Total Fees', f"{total_fees:,.0f}"],
        ['Amount Paid', f"{float(total_paid):,.0f}"],
        ['Balance', f"{balance:,.0f}"],
    ]
    fee_table = Table(fee_data, colWidths=[250, 150])
    fee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(fee_table)
    elements.append(Spacer(1, 18))
    
    # Payment history
    elements.append(Paragraph("<b>Payment History</b>", styles['Heading3']))
    elements.append(Spacer(1, 6))
    
    try:
        from django.db import connections
        with connections['school_db'].cursor() as cursor:
            cursor.execute("""
                SELECT payment_date, payment_method, amount_paid, term, academic_year
                FROM payments WHERE payment_code = %s
                ORDER BY payment_date DESC LIMIT 20
            """, [student.payment_code])
            rows = cursor.fetchall()
            
            if rows:
                history_data = [['Date', 'Method', 'Amount (UGX)', 'Term']]
                for row in rows:
                    history_data.append([
                        str(row[0])[:10],
                        row[1] or 'N/A',
                        f"{float(row[2]):,.0f}",
                        f"{row[3]} {row[4]}"
                    ])
                
                hist_table = Table(history_data, colWidths=[90, 140, 130, 100])
                hist_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ]))
                elements.append(hist_table)
            else:
                elements.append(Paragraph("No payment records found.", styles['Normal']))
    except Exception as e:
        elements.append(Paragraph(f"Payment history unavailable.", styles['Normal']))
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(f"Generated: {timezone.now().strftime('%d/%m/%Y %H:%M')} | OneCard System", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="statement_{payment_code}.pdf"'
    return response

@csrf_exempt
def public_statement_by_card_pdf(request):
    """Public API: Download PDF statement by student card ID."""
    api_key = request.GET.get('api_key', '')
    student_id = request.GET.get('student_id', '').strip()
    
    if not api_key or not student_id:
        return HttpResponse('Invalid request', status=400)
    
    try:
        APIClient.objects.get(api_key=api_key, is_active=True)
    except APIClient.DoesNotExist:
        return HttpResponse('Unauthorized', status=403)
    
    # Clean QR data
    if ':v' in student_id:
        student_id = student_id.split(':v')[0]
    
    try:
        student = Student.objects.get(id=student_id, status='active')
    except Student.DoesNotExist:
        return HttpResponse('Student not found', status=404)
    
    # Redirect to the payment_code version
    return public_statement_pdf_internal(student.payment_code)


def public_statement_pdf_internal(payment_code):
    """Internal function to generate PDF statement."""
    try:
        student = Student.objects.get(payment_code=payment_code, status='active')
    except Student.DoesNotExist:
        return HttpResponse('Student not found', status=404)
    
    info = get_student_info_from_existing_db(student.admission_number)
    if not info:
        return HttpResponse('Student data unavailable', status=503)
    
    total_paid = get_payment_balance(student.payment_code)
    student_category = student.category if hasattr(student, 'category') else 'day'
    fee = FeeStructure.objects.filter(class_name=info['class'], category=student_category).first()
    total_fees = float(fee.total_fees) if fee else 800000
    balance = total_fees - float(total_paid)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    
    elements.append(Paragraph("JINJA SENIOR SECONDARY SCHOOL", styles['Title']))
    elements.append(Paragraph("Fee Statement", styles['Heading2']))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"<b>Student:</b> {info['name']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Class:</b> {info['class']} {info['stream']} | <b>Category:</b> {student_category.title()}", styles['Normal']))
    elements.append(Paragraph(f"<b>Payment Code:</b> {payment_code}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date:</b> {timezone.now().strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    fee_data = [
        ['Description', 'Amount (UGX)'],
        ['Total Fees', f"{total_fees:,.0f}"],
        ['Amount Paid', f"{float(total_paid):,.0f}"],
        ['Balance', f"{balance:,.0f}"],
    ]
    fee_table = Table(fee_data, colWidths=[250, 150])
    fee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(fee_table)
    elements.append(Spacer(1, 18))
    
    elements.append(Paragraph("<b>Payment History</b>", styles['Heading3']))
    elements.append(Spacer(1, 6))
    
    try:
        from django.db import connections
        with connections['school_db'].cursor() as cursor:
            cursor.execute("""
                SELECT payment_date, payment_method, amount_paid, term, academic_year
                FROM payments WHERE payment_code = %s
                ORDER BY payment_date DESC LIMIT 20
            """, [student.payment_code])
            rows = cursor.fetchall()
            
            if rows:
                history_data = [['Date', 'Method', 'Amount (UGX)', 'Term']]
                for row in rows:
                    history_data.append([
                        str(row[0])[:10],
                        row[1] or 'N/A',
                        f"{float(row[2]):,.0f}",
                        f"{row[3]} {row[4]}"
                    ])
                
                hist_table = Table(history_data, colWidths=[90, 140, 130, 100])
                hist_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ]))
                elements.append(hist_table)
            else:
                elements.append(Paragraph("No payment records found.", styles['Normal']))
    except Exception:
        elements.append(Paragraph("Payment history unavailable.", styles['Normal']))
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(f"Generated: {timezone.now().strftime('%d/%m/%Y %H:%M')} | OneCard System", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="statement_{payment_code}.pdf"'
    return response


# ============================================================
# INTERNAL API (Login required)
# ============================================================

from core.cache_utils import invalidate_cache, make_key

@login_required
@require_POST
def process_scan(request):
    """Process a QR code scan — attendance, balance, pass-out, or meal tracking."""
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        location = data.get('location', 'Main Gate')
        mode = data.get('mode', 'attendance_balance')
        
        if not student_id:
            return JsonResponse({'success': False, 'error': 'No student ID provided'}, status=400)
        
        qr_version = 1
        if ':v' in student_id:
            parts = student_id.split(':v')
            student_id = parts[0]
            try: qr_version = int(parts[1])
            except (ValueError, IndexError): qr_version = 1
        
        try:
            student = Student.objects.select_related('template').get(id=student_id, status='active')
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Student not found or inactive'})
        
        if qr_version < student.card_version:
            return JsonResponse({
                'success': False,
                'error': f'CARD REPLACED — This card (v{qr_version}) was replaced on {student.last_reprint_date}. Current card is v{student.card_version}.',
                'error_code': 'CARD_REPLACED',
            }, status=410)
        
        info = get_student_info_from_existing_db(student.admission_number)
        if not info:
            return JsonResponse({'success': False, 'error': 'Cannot fetch student data.', 'error_code': 'DB_UNAVAILABLE'}, status=503)
        
        photo_url = build_photo_url(request, info.get('photo', ''))
        
        today = date.today()
        school = student.school
        
        already_marked = Attendance.objects.filter(student=student, scan_date=today).exists()
        if not already_marked:
            Attendance.objects.create(
                student=student, scan_date=today,
                time_in=datetime.now().time(), scan_location=location,
                marked_by=request.user.get_full_name() or request.user.username
            )
            # Invalidate caches after new attendance
            invalidate_cache(
                make_key('present', school.id, today),
                make_key('gate_present', school.id, today),
                make_key('attendance_report', school.id, today),
            )
        attendance_marked = not already_marked
        
        if mode == 'pass_out':
            existing = MovementLog.objects.filter(student=student, exit_date=today, time_in__isnull=True).first()
            
            if existing:
                now_time = datetime.now().time()
                existing.time_in = now_time
                existing.save()
                # Invalidate movement caches
                invalidate_cache(
                    make_key('outside', school.id, today),
                    make_key('gate_outside', school.id, today),
                )
                out_dt = datetime.combine(today, existing.time_out)
                in_dt = datetime.combine(today, now_time)
                diff = in_dt - out_dt
                hours = diff.seconds // 3600
                minutes = (diff.seconds % 3600) // 60
                
                return JsonResponse({
                    'success': True,
                    'student': {'id': student.id, 'name': info['name'], 'class': info['class'], 'stream': info['stream'], 'admission': student.admission_number, 'photo': photo_url},
                    'movement': {'action': 'return', 'time_out': str(existing.time_out), 'time_in': str(now_time), 'duration': f'{hours}h {minutes}m'},
                    'attendance': {'marked': attendance_marked, 'already_marked': already_marked}
                })
            else:
                # Invalidate movement caches for new exit
                invalidate_cache(
                    make_key('outside', school.id, today),
                    make_key('gate_outside', school.id, today),
                )
                return JsonResponse({
                    'success': True,
                    'student': {'id': student.id, 'name': info['name'], 'class': info['class'], 'stream': info['stream'], 'admission': student.admission_number, 'photo': photo_url},
                    'movement': {'action': 'exit'},
                    'attendance': {'marked': attendance_marked, 'already_marked': already_marked}
                })
        
        if mode == 'meal_tracking':
            meal_settings, _ = MealTimeSettings.objects.get_or_create(id=1)
            now = datetime.now().time()
            meal_type = meal_settings.get_current_meal()
            
            if not meal_type:
                return JsonResponse({'success': False, 'error': 'Not meal time.', 'error_code': 'NOT_MEAL_TIME'})
            
            student_category = student.category if hasattr(student, 'category') else 'day'
            
            if student_category == 'day' and meal_type != 'lunch':
                violation_type = 'day_supper' if meal_type == 'supper' else 'day_breakfast'
                MealViolation.objects.create(student=student, meal_type=meal_type, violation_type=violation_type, location=location)
                invalidate_cache(make_key('meal_violations', school.id))
                return JsonResponse({'success': False, 'error': f'DAY SCHOLAR — {meal_type.title()} not available.'})
            
            already_eaten = MealLog.objects.filter(student=student, meal_date=today, meal_type=meal_type).first()
            if already_eaten:
                MealViolation.objects.create(student=student, meal_type=meal_type, violation_type='double_serving', location=location)
                invalidate_cache(make_key('meal_violations', school.id))
                return JsonResponse({'success': False, 'error': f'ALREADY SERVED at {already_eaten.time_scanned}'})
            
            # ... rest of meal tracking (unchanged) ...
            MealLog.objects.create(student=student, meal_date=today, meal_type=meal_type, time_scanned=now, location=location, marked_by=request.user.get_full_name() or request.user.username)
            invalidate_cache(make_key('meal_violations', school.id))
            
            return JsonResponse({
                'success': True,
                'meal': {'type': meal_type, 'category': student_category, 'time': str(now)},
                'student': {'id': student.id, 'name': info['name'], 'class': info['class'], 'stream': info['stream'], 'photo': photo_url},
                'attendance': {'marked': attendance_marked, 'already_marked': already_marked}
            })
        
        # Attendance / Balance mode
        total_paid = get_payment_balance(student.payment_code)
        student_category = student.category if hasattr(student, 'category') else 'day'
        fee = FeeStructure.objects.filter(class_name=info['class'], category=student_category).first()
        
        if not fee:
            return JsonResponse({'success': False, 'error': f'Fee structure not set.'}, status=400)
        
        total_fees = float(fee.total_fees)
        balance = total_fees - float(total_paid)
        
        if balance <= 0 and float(total_paid) > 0: status = 'CLEARED'
        elif float(total_paid) > total_fees: status = 'OVERPAID'
        elif float(total_paid) == 0: status = 'NOT PAID'
        else: status = 'NOT CLEARED'
        
        return JsonResponse({
            'success': True,
            'student': {'id': student.id, 'name': info['name'], 'class': info['class'], 'stream': info['stream'], 'admission': student.admission_number, 'payment_code': student.payment_code, 'photo': photo_url},
            'fees': {'total': total_fees, 'paid': float(total_paid), 'balance': balance, 'status': status},
            'attendance': {'marked': attendance_marked, 'already_marked': already_marked}
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
    
    if cls: students = [s for s in students if s['current_class'] == cls]
    if stream: students = [s for s in students if s['stream'] == stream]
    if search: students = [s for s in students if search in s['full_name'].lower() or search in s['admission_number'].lower()]
    
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 50))
    total = len(students)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    
    return JsonResponse({
        'students': students[start:end], 'total': total, 'page': page, 'total_pages': total_pages,
        'imported_count': len(imported_ids), 'remaining_count': total,
    })


@login_required
def api_import_progress(request):
    """Get current import progress from cache."""
    progress = cache.get('import_progress', {
        'total': 0, 'imported': 0, 'skipped': 0, 'errors': 0,
        'running': False, 'message': 'No import running'
    })
    return JsonResponse(progress)


from core.cache_utils import invalidate_cache, make_key

@login_required
@require_POST
def api_import_students(request):
    """Import selected students via AJAX with batch processing and progress tracking."""
    try:
        data = json.loads(request.body)
        selected = data.get('students', [])
        import_all = data.get('import_all', False)
        
        school = _get_school(request)
        
        if import_all:
            all_school = fetch_students_from_existing_db()
            imported_ids = set(Student.objects.filter(school=school).values_list('admission_number', flat=True))
            selected = [s['admission_number'] for s in all_school if s['admission_number'] not in imported_ids]
        
        if not selected:
            return JsonResponse({'success': False, 'message': 'No students to import.'})
        
        total = len(selected)
        cache.set('import_progress', {
            'total': total, 'imported': 0, 'skipped': 0, 'errors': 0,
            'running': True, 'message': f'Starting import of {total} students...'
        }, 600)
        
        all_school_students = fetch_students_from_existing_db()
        school_dict = {s['admission_number']: s for s in all_school_students}
        
        imported = skipped = errors = 0
        
        for i, admission_number in enumerate(selected):
            try:
                if Student.objects.filter(school=school, admission_number=admission_number).exists():
                    skipped += 1; continue
                student_data = school_dict.get(admission_number)
                if not student_data: errors += 1; continue
                
                student_id = get_next_student_id()
                qr_file = generate_qr_for_student(student_id)
                
                student = Student(
                    school=school,
                    id=student_id, admission_number=admission_number,
                    payment_code=student_data['payment_code'],
                    category=student_data.get('category', 'day'),
                    status='active', card_version=1
                )
                student.qr_code.save(f'{student_id}.png', qr_file, save=False)
                student.save()
                imported += 1
            except Exception as e:
                logger.error(f"Import error for {admission_number}: {e}")
                errors += 1
            
            if i % 50 == 0:
                pct = round((i / total) * 100) if total > 0 else 0
                cache.set('import_progress', {
                    'total': total, 'imported': imported, 'skipped': skipped, 'errors': errors,
                    'running': True, 'percent': pct,
                    'message': f'Importing... {imported}/{total} ({pct}%)'
                }, 600)
        
        # Invalidate caches after import
        invalidate_cache(
            make_key('total_students', school.id),
            make_key('student_list', school.id),
            make_key('fee_report', school.id),
            make_key('attendance_report', school.id, date.today()),
        )
        
        cache.set('import_progress', {
            'total': total, 'imported': imported, 'skipped': skipped, 'errors': errors,
            'running': False, 'percent': 100,
            'message': f'Complete! Imported: {imported} | Skipped: {skipped} | Errors: {errors}'
        }, 600)
        
        return JsonResponse({
            'success': True, 'message': f'Imported: {imported} | Skipped: {skipped} | Errors: {errors}',
            'imported': Student.objects.filter(school=school, status='active').count(),
            'total': total, 'imported_count': imported, 'skipped': skipped, 'errors': errors
        })
    except Exception as e:
        logger.error(f"Import batch error: {str(e)}", exc_info=True)
        cache.set('import_progress', {'running': False, 'message': f'Error: {str(e)}'}, 600)
        return JsonResponse({'success': False, 'message': str(e)})