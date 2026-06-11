from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Student
from .services import generate_qr_for_student, get_next_student_id, fetch_students_from_existing_db
import logging

logger = logging.getLogger('onecard')


@login_required
def import_students(request):
    """Import students from existing school database."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        return handle_import(request)
    
    # Fetch real students from existing DB
    students = fetch_students_from_existing_db()
    
    if not students:
        messages.info(request, 'No students found in school database, or database connection not configured.')
    
    return render(request, 'admin_dashboard/import.html', {'students': students})


def handle_import(request):
    """Process student import."""
    selected = request.POST.getlist('selected_students')
    if not selected:
        messages.error(request, 'No students selected.')
        return redirect('import_students')
    
    imported = 0
    errors = []
    
    for admission_number in selected:
        try:
            # Skip if already imported
            if Student.objects.filter(admission_number=admission_number).exists():
                continue
            
            full_name = request.POST.get(f'name_{admission_number}', '')
            payment_code = request.POST.get(f'payment_{admission_number}', '')
            
            student_id = get_next_student_id()
            qr_file = generate_qr_for_student(student_id)
            
            student = Student(
                id=student_id,
                admission_number=admission_number,
                payment_code=payment_code,
                status='active'
            )
            student.qr_code.save(f'{student_id}.png', qr_file)
            student.save()
            imported += 1
            
        except Exception as e:
            errors.append(f'{admission_number}: {str(e)}')
            logger.error(f"Import error for {admission_number}: {e}")
    
    if imported > 0:
        messages.success(request, f'Successfully imported {imported} students.')
    if errors:
        messages.warning(request, f'{len(errors)} errors occurred.')
    
    return redirect('view_students')


@login_required
def view_students(request):
    """View all imported students."""
    if request.user.role not in ['super_admin', 'admin', 'bursar']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    students = Student.objects.select_related('template').all()
    return render(request, 'admin_dashboard/students.html', {'students': students})


def error_404(request, exception=None):
    """Custom 404 page."""
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    """Custom 500 page."""
    return render(request, 'errors/500.html', status=500)


def error_403(request, exception=None):
    """Custom 403 page."""
    return render(request, 'errors/403.html', status=403)


@login_required
def backup_now(request):
    """Trigger a manual backup."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    from django.core.management import call_command
    try:
        call_command('backup')
        messages.success(request, 'Backup completed successfully!')
    except Exception as e:
        messages.error(request, f'Backup failed: {e}')
    
    return redirect('dashboard')