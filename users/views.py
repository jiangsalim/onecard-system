from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date
import logging

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
                return redirect('dashboard')
            else:
                messages.error(request, 'Account disabled. Contact admin.')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'auth/login.html')


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
    from core.services import get_payment_balance
    from fees.models import FeeStructure
    from core.services import get_student_info_from_existing_db

    today = date.today()
    total = Student.objects.filter(status='active').count()
    present = Attendance.objects.filter(scan_date=today).count()

    # Calculate not-cleared count with Day/Hostel fee structure
    not_cleared = 0
    fee_structures = {}
    for f in FeeStructure.objects.filter(term='Term 2', academic_year='2026'):
        key = f"{f.class_name}_{f.category}"
        fee_structures[key] = float(f.total_fees)
    
    if total > 0:
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
        return render(request, 'admin_dashboard/home.html', {'stats': stats})
    elif role == 'bursar':
        return redirect('bursar_dashboard')
    elif role == 'gate_staff':
        return redirect('gate_dashboard')
    elif role == 'class_teacher':
        return redirect('teacher_dashboard')
    return render(request, 'admin_dashboard/home.html', {'stats': stats})


@login_required
def bursar_dashboard(request):
    return render(request, 'admin_dashboard/bursar.html')


@login_required
def gate_dashboard(request):
    return render(request, 'admin_dashboard/gate.html')


@login_required
def teacher_dashboard(request):
    return render(request, 'admin_dashboard/teacher.html')


@login_required
def scanner_view(request):
    """Scanner page for gate staff and bursar."""
    return render(request, 'admin_dashboard/scanner.html')