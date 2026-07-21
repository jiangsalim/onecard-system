from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Student
from .services import generate_qr_for_student, get_next_student_id, fetch_students_from_existing_db
from core.mobile_utils import render_mobile_or_desktop
import logging

import os
print(f"========== DEBUG = {os.environ.get('DEBUG', 'NOT SET')} ==========")

logger = logging.getLogger('onecard')


@login_required
def import_students(request):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    if request.method == 'POST':
        return handle_import(request)
    students = fetch_students_from_existing_db()
    if not students:
        messages.info(request, 'No students found in school database.')
    return render_mobile_or_desktop(request, 'admin_dashboard/import.html', 'mobile/import_students.html', {'students': students})


def handle_import(request):
    selected = request.POST.getlist('selected_students')
    if not selected:
        messages.error(request, 'No students selected.')
        return redirect('import_students')
    imported = 0; errors = []
    for admission_number in selected:
        try:
            if Student.objects.filter(admission_number=admission_number).exists(): continue
            full_name = request.POST.get(f'name_{admission_number}', '')
            payment_code = request.POST.get(f'payment_{admission_number}', '')
            student_id = get_next_student_id()
            qr_file = generate_qr_for_student(student_id)
            student = Student(id=student_id, admission_number=admission_number, payment_code=payment_code, full_name=full_name, parent_name='', current_class='', stream='', gender='', status='active')
            student.qr_code.save(f'{student_id}.png', qr_file)
            student.save()
            imported += 1
        except Exception as e:
            errors.append(f'{admission_number}: {str(e)}')
            logger.error(f"Import error for {admission_number}: {e}")
    if imported > 0: messages.success(request, f'Imported {imported} students.')
    if errors: messages.warning(request, f'{len(errors)} errors.')
    return redirect('view_students')


@login_required
def view_students(request):
    if request.user.role not in ['super_admin', 'admin', 'bursar', 'class_teacher']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    from core.services import fetch_students_from_existing_db
    
    # Get students from OneCard
    students = list(Student.objects.select_related('template').all())
    
    # Get school info for names/classes
    all_school = fetch_students_from_existing_db()
    school_dict = {s['admission_number']: s for s in all_school}
    
    # Enrich with school data
    for student in students:
        info = school_dict.get(student.admission_number, {})
        student.school_name = info.get('full_name', '—')
        student.school_class = info.get('current_class', '—')
        student.school_stream = info.get('stream', '')
    
    # Sort by ID
    def sort_key(s):
        try: return int(s.id.replace('STU-', ''))
        except: return 0
    students.sort(key=sort_key)
    
    # Get filters
    class_filter = request.GET.get('class', '')
    stream_filter = request.GET.get('stream', '')
    category_filter = request.GET.get('category', '')
    search = request.GET.get('search', '').lower()
    
    # Apply filters
    if class_filter:
        students = [s for s in students if s.school_class == class_filter]
    if stream_filter:
        students = [s for s in students if s.school_stream == stream_filter]
    if category_filter:
        students = [s for s in students if s.category == category_filter]
    if search:
        students = [s for s in students if 
            search in s.id.lower() or 
            search in s.admission_number.lower() or 
            search in s.school_name.lower()]
    
    # Get unique classes and streams for filter dropdowns
    all_classes = sorted(set(s.school_class for s in students if s.school_class != '—'))
    all_streams = sorted(set(s.school_stream for s in students if s.school_stream))
    
    return render_mobile_or_desktop(request, 'admin_dashboard/students.html', 'mobile/students.html', {
        'students': students,
        'total': len(students),
        'classes': all_classes,
        'streams': all_streams,
        'class_filter': class_filter,
        'stream_filter': stream_filter,
        'category_filter': category_filter,
        'search': search,
    })

@login_required
def edit_student(request, student_id):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        student.category = request.POST.get('category', student.category)
        student.status = request.POST.get('status', student.status)
        student.save()
        messages.success(request, f'Student {student.id} updated!')
        return redirect('view_students')
    return render_mobile_or_desktop(request, 'admin_dashboard/edit_student.html', 'mobile/edit_student.html', {'student': student})


def error_404(request, exception=None):
    try:
        return render_mobile_or_desktop(request, 'errors/404.html', 'mobile/error_404.html', status=404)
    except Exception:
        return render(request, 'errors/404.html', status=404)

def error_500(request):
    try:
        return render_mobile_or_desktop(request, 'errors/500.html', 'mobile/error_500.html', status=500)
    except Exception:
        return render(request, 'errors/500.html', status=500)

def error_403(request, exception=None):
    try:
        return render_mobile_or_desktop(request, 'errors/403.html', 'mobile/error_403.html', status=403)
    except Exception:
        return render(request, 'errors/403.html', status=403)

@login_required
def backup_now(request):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    from django.core.management import call_command
    from django.http import HttpResponse
    from io import StringIO
    import os
    from django.conf import settings
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Try Django dumpdata (works everywhere, no mysqldump needed)
    try:
        backup_content = StringIO()
        call_command('dumpdata',
            '--exclude', 'auth.permission',
            '--exclude', 'contenttypes',
            '--exclude', 'sessions.session',
            stdout=backup_content
        )
        
        filename = f'onecard_backup_{timestamp}.json'
        response = HttpResponse(backup_content.getvalue(), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        messages.success(request, f'Backup downloaded! ({filename})')
        return response
    except Exception as e:
        # Fallback: try the management command
        try:
            call_command('backup')
            messages.success(request, 'Backup saved to server backups folder!')
        except Exception as e2:
            messages.error(request, f'Backup failed: {e2}')
        
        return redirect('dashboard')


def scan_redirect(request, student_id):
    mode = request.GET.get('mode', '')
    url = f"/scanner/?id={student_id}"
    if mode: url += f"&mode={mode}"
    return redirect(url)


@login_required
def import_students_excel(request):
    """Import students from Excel file (Standalone mode)."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST' and request.FILES.get('file'):
        import openpyxl
        from io import BytesIO
        
        file = request.FILES['file']
        try:
            wb = openpyxl.load_workbook(BytesIO(file.read()))
            ws = wb.active
        except Exception:
            messages.error(request, 'Invalid file format.')
            return redirect('import_students_excel')
        
        imported = errors = skipped = 0
        
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[0]: continue
            try:
                admission_number = str(row[0]).strip()
                full_name = str(row[1]).strip() if row[1] else ''
                current_class = str(row[2]).strip() if row[2] else ''
                stream = str(row[3]).strip() if row[3] else ''
                payment_code = str(row[4]).strip() if row[4] else ''
                gender = str(row[5]).strip()[:1] if len(row) > 5 and row[5] else ''
                category = str(row[6]).strip() if len(row) > 6 and row[6] else 'day'
                
                if Student.objects.filter(admission_number=admission_number).exists():
                    skipped += 1; continue
                
                if not payment_code: payment_code = admission_number
                
                student_id = get_next_student_id()
                qr_file = generate_qr_for_student(student_id)
                
                student = Student(
                    id=student_id, admission_number=admission_number,
                    payment_code=payment_code, full_name=full_name,

                    current_class=current_class, stream=stream,
                    gender=gender, category=category,
                    status='active', card_version=1,
                )
                student.qr_code.save(f'{student_id}.png', qr_file, save=False)
                student.save()
                imported += 1
            except Exception as e:
                errors += 1
        
        messages.success(request, f'Imported: {imported} | Skipped: {skipped} | Errors: {errors}')
        return redirect('view_students')
    
    return render(request, 'core/import_excel.html', {})

@csrf_exempt
def google_auth_receiver(request):
    """Receive Google auth data and log user in."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            
            user = User.objects.get(email__iexact=email, is_active=True)
            
            # Use Django's login
            from django.contrib.auth import login as django_login
            django_login(request, user)
            
            messages.success(request, f'Welcome, {user.get_full_name() or user.username}!')
            return JsonResponse({'success': True, 'redirect': '/dashboard/'})
            
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'No account found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False}, status=405)