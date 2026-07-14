from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Student
from .services import generate_qr_for_student, get_next_student_id, fetch_students_from_existing_db
from core.mobile_utils import render_mobile_or_desktop
import logging
from linecache import cache

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
            student = Student(id=student_id, admission_number=admission_number, payment_code=payment_code, status='active')
            student.qr_code.save(f'{student_id}.png', qr_file)
            student.save()
            imported += 1
        except Exception as e:
            errors.append(f'{admission_number}: {str(e)}')
            logger.error(f"Import error for {admission_number}: {e}")
    if imported > 0: messages.success(request, f'Imported {imported} students.')
    if errors: messages.warning(request, f'{len(errors)} errors.')
    return redirect('view_students')


from core.cache_utils import get_or_set, make_key

@login_required
def view_students(request):
    if request.user.role not in ['super_admin', 'admin', 'bursar']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    school = _get_school(request)
    
    # Cache: Student list (10 min - rarely changes)
    def load_students():
        students = list(Student.objects.filter(school=school).select_related('template').all())
        students.sort(key=lambda s: int(s.id.replace('STU-', '')) if s.id.replace('STU-', '').isdigit() else 0)
        return students
    
    students = get_or_set(
        make_key('student_list', school.id),
        load_students,
        timeout=600
    )
    
    return render_mobile_or_desktop(request, 'admin_dashboard/students.html', 'mobile/students.html', {'students': students})

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
    return render_mobile_or_desktop(request, 'errors/404.html', 'mobile/error_404.html', status=404)

def error_500(request):
    return render_mobile_or_desktop(request, 'errors/500.html', 'mobile/error_500.html', status=500)

def error_403(request, exception=None):
    return render_mobile_or_desktop(request, 'errors/403.html', 'mobile/error_403.html', status=403)


@login_required
def backup_now(request):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    from django.core.management import call_command
    try:
        call_command('backup')
        messages.success(request, 'Backup completed!')
    except Exception as e:
        messages.error(request, f'Backup failed: {e}')
    return redirect('dashboard')


def scan_redirect(request, student_id):
    mode = request.GET.get('mode', '')
    url = f"/scanner/?id={student_id}"
    if mode: url += f"&mode={mode}"
    return redirect(url)