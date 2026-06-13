from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date
from django.core.cache import cache
import logging
from .models import User
from core.mobile_utils import render_mobile_or_desktop

logger = logging.getLogger('onecard')


def redirect_to_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Welcome, {user.get_full_name() or user.username}!')
                next_url = request.GET.get('next', '')
                if next_url:
                    return redirect(next_url)
                return redirect('dashboard')
            else:
                messages.error(request, 'Account disabled. Contact admin.')
        else:
            messages.error(request, 'Invalid username or password.')
    return render_mobile_or_desktop(request, 'auth/login.html', 'mobile/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out.')
    return redirect('login')


@login_required
def dashboard(request):
    """Role-based dashboard routing with live stats and auto-alerts."""
    from core.models import Student
    from attendance.models import Attendance
    from movement.models import MovementLog
    from core.services import get_payment_balance, get_student_info_from_existing_db
    from fees.models import FeeStructure

    today = date.today()
    total = Student.objects.filter(status='active').count()
    present = Attendance.objects.filter(scan_date=today).count()

    # Build fee structures
    fee_structures = {}
    for f in FeeStructure.objects.filter(term='Term 2', academic_year='2026'):
        key = f"{f.class_name}_{f.category}"
        fee_structures[key] = float(f.total_fees)

    # Try cached not_cleared count
    not_cleared = cache.get('not_cleared_count')
    if not_cleared is None:
        not_cleared = 0
        if total > 0 and fee_structures:
            for s in Student.objects.filter(status='active'):
                try:
                    info = get_student_info_from_existing_db(s.admission_number)
                    class_name = info['class'] if info else None
                    student_cat = getattr(s, 'category', 'day')
                    fee_key = f"{class_name}_{student_cat}" if class_name else None
                    total_fee = fee_structures.get(fee_key, 800000) if fee_key else 800000
                    paid = get_payment_balance(s.payment_code)
                    if float(paid) < total_fee:
                        not_cleared += 1
                except Exception:
                    pass
        # Cache for 30 minutes (1800 seconds)
        cache.set('not_cleared_count', not_cleared, 1800)

    stats = {
        'total': total,
        'present': present,
        'outside': MovementLog.objects.filter(exit_date=today, time_in__isnull=True).count(),
        'absent': total - present if total > present else 0,
        'not_cleared': not_cleared,
    }

    # Auto-generate alerts on dashboard visit
    try:
        from notifications.views import auto_check_alerts
        alerts = auto_check_alerts()
        if alerts > 0:
            logger.info(f"Auto-generated {alerts} notification(s)")
    except Exception as e:
        logger.warning(f"Auto-check alerts failed: {e}")

    role = request.user.role
    if role in ['super_admin', 'admin']:
        return render_mobile_or_desktop(request, 'admin_dashboard/home.html', 'mobile/admin_dashboard.html', {'stats': stats})
    elif role == 'bursar':
        return redirect('bursar_dashboard')
    elif role == 'gate_staff':
        return redirect('gate_dashboard')
    elif role == 'class_teacher':
        return redirect('teacher_dashboard')
    return render_mobile_or_desktop(request, 'admin_dashboard/home.html', 'mobile/admin_dashboard.html', {'stats': stats})


@login_required
def bursar_dashboard(request):
    return render_mobile_or_desktop(request, 'admin_dashboard/bursar.html', 'mobile/bursar_dashboard.html')


@login_required
def gate_dashboard(request):
    """Gate staff dashboard with live stats."""
    from core.models import Student
    from attendance.models import Attendance
    from movement.models import MovementLog
    
    today = date.today()
    total = Student.objects.filter(status='active').count()
    present = Attendance.objects.filter(scan_date=today).count()
    outside = MovementLog.objects.filter(exit_date=today, time_in__isnull=True).count()
    last_scan = Attendance.objects.filter(scan_date=today).order_by('-time_in').first()
    last_scan_time = last_scan.time_in.strftime('%H:%M') if last_scan else '--:--'
    
    stats = {
        'present': present,
        'outside': outside,
        'absent': total - present if total > present else 0,
        'last_scan': last_scan_time,
    }
    return render_mobile_or_desktop(request, 'admin_dashboard/gate.html', 'mobile/gate_dashboard.html', {'stats': stats})


@login_required
def teacher_dashboard(request):
    """Class teacher dashboard with live stats filtered to assigned class."""
    from core.models import Student
    from attendance.models import Attendance
    from movement.models import MovementLog
    from core.services import fetch_students_from_existing_db
    
    today = date.today()
    assigned_class = request.user.assigned_class
    assigned_stream = request.user.assigned_stream
    
    all_school = fetch_students_from_existing_db()
    class_admissions = [
        s['admission_number'] for s in all_school 
        if s['current_class'] == assigned_class 
        and (not assigned_stream or s['stream'] == assigned_stream)
    ]
    class_students = Student.objects.filter(admission_number__in=class_admissions, status='active')
    class_student_ids = class_students.values_list('id', flat=True)
    
    total_students = class_students.count()
    present_today = Attendance.objects.filter(student_id__in=class_student_ids, scan_date=today).count()
    
    stats = {
        'total': total_students,
        'present': present_today,
        'absent': total_students - present_today if total_students > present_today else 0,
        'outside': MovementLog.objects.filter(student_id__in=class_student_ids, exit_date=today, time_in__isnull=True).count(),
        'rate': round((present_today / total_students * 100) if total_students > 0 else 0, 1),
        'class_name': f"{assigned_class} {assigned_stream}",
    }
    return render_mobile_or_desktop(request, 'admin_dashboard/teacher.html', 'mobile/teacher_dashboard.html', {'stats': stats})


@login_required
def scanner_view(request):
    """Scanner page for gate staff and bursar."""
    return render_mobile_or_desktop(request, 'admin_dashboard/scanner.html', 'mobile/scanner.html')


@login_required
def user_management(request):
    """Super Admin: Manage all users."""
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    users = User.objects.all().order_by('role', 'username')
    return render_mobile_or_desktop(request, 'users/list.html', 'mobile/users_list.html', {'users': users})


@login_required
def add_user(request):
    """Super Admin: Add new user."""
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email', '')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        role = request.POST.get('role')
        assigned_location = request.POST.get('assigned_location', '')
        assigned_class = request.POST.get('assigned_class', '')
        assigned_stream = request.POST.get('assigned_stream', '')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            return redirect('add_user')
        if not password:
            messages.error(request, 'Password is required.')
            return redirect('add_user')
        
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name, role=role,
            assigned_location=assigned_location, assigned_class=assigned_class,
            assigned_stream=assigned_stream, is_active=True, is_staff=True,
        )
        messages.success(request, f'User "{username}" created successfully!')
        return redirect('user_management')
    return render_mobile_or_desktop(request, 'users/form.html', 'mobile/users_form.html', {'edit_mode': False})


@login_required
def edit_user(request, user_id):
    """Super Admin: Edit existing user."""
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    target_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        target_user.username = request.POST.get('username', target_user.username)
        target_user.email = request.POST.get('email', '')
        target_user.first_name = request.POST.get('first_name', '')
        target_user.last_name = request.POST.get('last_name', '')
        target_user.role = request.POST.get('role', target_user.role)
        target_user.assigned_location = request.POST.get('assigned_location', '')
        target_user.assigned_class = request.POST.get('assigned_class', '')
        target_user.assigned_stream = request.POST.get('assigned_stream', '')
        new_password = request.POST.get('password')
        if new_password:
            target_user.set_password(new_password)
        target_user.save()
        messages.success(request, f'User "{target_user.username}" updated!')
        return redirect('user_management')
    return render_mobile_or_desktop(request, 'users/form.html', 'mobile/users_form.html', {'edit_mode': True, 'target_user': target_user})


@login_required
def delete_user(request, user_id):
    """Super Admin: Delete a user."""
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('user_management')
    if target_user.role == 'super_admin' and User.objects.filter(role='super_admin').count() <= 1:
        messages.error(request, 'Cannot delete the last Super Admin.')
        return redirect('user_management')
    if request.method == 'POST':
        username = target_user.username
        target_user.delete()
        messages.success(request, f'User "{username}" deleted.')
        return redirect('user_management')
    return render_mobile_or_desktop(request, 'users/delete_confirm.html', 'mobile/users_delete.html', {'target_user': target_user})