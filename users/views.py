from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date
from django.core.cache import cache
import logging
from .models import User
from core.mobile_utils import render_mobile_or_desktop
from core.decorators import reauth_required
import random
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.http import JsonResponse


logger = logging.getLogger('onecard')


def redirect_to_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

def _get_school(request):
    """Helper to get current user's school."""
    if request.user.is_authenticated:
        if hasattr(request.user, 'school') and request.user.school:
            return request.user.school
    return None


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Check rate limiting
    if hasattr(request, 'rate_limited') and request.rate_limited:
        retry_after = getattr(request, 'rate_limit_retry_after', 300)
        return render_mobile_or_desktop(request, 'auth/login.html', 'mobile/login.html', {
            'rate_limited': True,
            'retry_after': retry_after,
        })
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                # Reset failed login counter on success
                from core.middleware import reset_failed_logins
                reset_failed_logins(user.username)
                
                login(request, user)
                messages.success(request, f'Welcome, {user.get_full_name() or user.username}!')
                next_url = request.GET.get('next', '')
                if next_url:
                    return redirect(next_url)
                return redirect('dashboard')
            else:
                messages.error(request, 'Account disabled. Contact admin.')
        else:
            # Record failed login attempt
            from core.middleware import record_failed_login
            record_failed_login(username)
            messages.error(request, 'Invalid username or password.')
    
    return render_mobile_or_desktop(request, 'auth/login.html', 'mobile/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out.')
    return redirect('login')

@login_required
def dashboard(request):
    """Role-based dashboard routing with live stats, alerts, and meal violations."""
    from core.models import Student
    from attendance.models import Attendance, MealViolation
    from movement.models import MovementLog
    from core.services import get_payment_balance, get_student_info_from_existing_db
    from fees.models import FeeStructure

    today = date.today()
    total = Student.objects.filter(status='active').count()
    present = Attendance.objects.filter(scan_date=today).count()

    fee_structures = {}
    for f in FeeStructure.objects.filter(term='Term 2', academic_year='2026'):
        key = f"{f.class_name}_{f.category}"
        fee_structures[key] = float(f.total_fees)

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
        cache.set('not_cleared_count', not_cleared, 1800)

    stats = {
        'total': total, 'present': present,
        'outside': MovementLog.objects.filter(exit_date=today, time_in__isnull=True).count(),
        'absent': total - present if total > present else 0,
        'not_cleared': not_cleared,
    }

    meal_violations = MealViolation.objects.filter(resolved=False).select_related('student').order_by('-occurred_at')[:5]

    role = request.user.role
    if role in ['super_admin', 'admin']:
        return render_mobile_or_desktop(request, 'admin_dashboard/home.html', 'mobile/admin_dashboard.html', {
            'stats': stats, 'meal_violations': meal_violations,
        })
    elif role == 'bursar': return redirect('bursar_dashboard')
    elif role == 'gate_staff': return redirect('gate_dashboard')
    elif role == 'class_teacher': return redirect('teacher_dashboard')
    return render_mobile_or_desktop(request, 'admin_dashboard/home.html', 'mobile/admin_dashboard.html', {
        'stats': stats, 'meal_violations': meal_violations,
    })




@login_required
def bursar_dashboard(request):
    return render_mobile_or_desktop(request, 'admin_dashboard/bursar.html', 'mobile/bursar_dashboard.html')


@login_required
def gate_dashboard(request):
    from core.models import Student
    from attendance.models import Attendance
    from movement.models import MovementLog
    
    today = date.today()
    total = Student.objects.filter(status='active').count()
    present = Attendance.objects.filter(scan_date=today).count()
    outside = MovementLog.objects.filter(exit_date=today, time_in__isnull=True).count()
    last_scan = Attendance.objects.filter(scan_date=today).order_by('-time_in').first()
    last_scan_time = last_scan.time_in.strftime('%H:%M') if last_scan else '--:--'
    
    return render_mobile_or_desktop(request, 'admin_dashboard/gate.html', 'mobile/gate_dashboard.html', {
        'stats': {'present': present, 'outside': outside, 'absent': total - present if total > present else 0, 'last_scan': last_scan_time}
    })

@login_required
def teacher_dashboard(request):
    """Class teacher dashboard with charts, gender stats, absent alerts & notification prefs."""
    from core.models import Student
    from attendance.models import Attendance
    from movement.models import MovementLog
    from core.services import fetch_students_from_existing_db
    from notifications.models import TeacherNotificationSetting, DismissedAlert
    import json
    from datetime import timedelta
    
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
    
    # Gender breakdown
    male_admissions = [s['admission_number'] for s in all_school
                       if s['current_class'] == assigned_class
                       and (not assigned_stream or s['stream'] == assigned_stream)
                       and s.get('gender') == 'M']
    female_admissions = [s['admission_number'] for s in all_school
                         if s['current_class'] == assigned_class
                         and (not assigned_stream or s['stream'] == assigned_stream)
                         and s.get('gender') == 'F']
    males_count = len(male_admissions)
    females_count = len(female_admissions)
    
    # Weekly attendance for bar chart (last 7 days)
    weekly_labels = []
    weekly_present = []
    weekly_absent = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = Attendance.objects.filter(student_id__in=class_student_ids, scan_date=d).count()
        weekly_labels.append(d.strftime('%a'))
        weekly_present.append(count)
        weekly_absent.append(total_students - count if total_students > count else 0)
    
    # Students with 3+ consecutive absences (only undismissed)
    already_dismissed = DismissedAlert.objects.filter(
        user=request.user, alert_date=today
    ).values_list('student_id', flat=True)
    
    absent_streaks = []
    for student in class_students:
        # Skip if already dismissed today
        if student.id in already_dismissed:
            continue
        
        recent_days = [today - timedelta(days=i) for i in range(3)]
        absences = 0
        for d in recent_days:
            if not Attendance.objects.filter(student=student, scan_date=d).exists():
                absences += 1
        if absences >= 3:
            info = next((s for s in all_school if s['admission_number'] == student.admission_number), None)
            absent_streaks.append({
                'id': student.id,
                'name': info['full_name'] if info else str(student.id),
                'admission': student.admission_number,
                'days': absences,
            })
    
    # Count dismissed today (for the "previously dismissed" section)
    dismissed_count = DismissedAlert.objects.filter(
        user=request.user, alert_date=today
    ).count()
    
    # Notification settings (get or create)
    notif_settings, _ = TeacherNotificationSetting.objects.get_or_create(user=request.user)
    
    # Handle POST for saving notification preferences
    if request.method == 'POST':
        notif_settings.alert_3_consecutive_absences = request.POST.get('alert_3_consecutive') == 'on'
        notif_settings.alert_attendance_below_75 = request.POST.get('alert_below_75') == 'on'
        notif_settings.alert_5_absences_term = request.POST.get('alert_5_absences') == 'on'
        notif_settings.save()
        messages.success(request, 'Notification preferences saved!')
    
    stats = {
        'total': total_students,
        'present': present_today,
        'absent': total_students - present_today if total_students > present_today else 0,
        'outside': MovementLog.objects.filter(student_id__in=class_student_ids, exit_date=today, time_in__isnull=True).count(),
        'rate': round((present_today / total_students * 100) if total_students > 0 else 0, 1),
        'class_name': f"{assigned_class} {assigned_stream}",
    }
    
    return render_mobile_or_desktop(request, 'admin_dashboard/teacher.html', 'mobile/teacher_dashboard.html', {
        'stats': stats,
        'males_count': males_count,
        'females_count': females_count,
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_present': json.dumps(weekly_present),
        'weekly_absent': json.dumps(weekly_absent),
        'absent_streaks': absent_streaks,
        'dismissed_count': dismissed_count,
        'notif_settings': notif_settings,
    })


@login_required
def dismiss_alert(request, student_id):
    """Teacher dismisses an absence alert for today."""
    from core.models import Student
    from notifications.models import DismissedAlert
    
    try:
        student = Student.objects.get(id=student_id)
        DismissedAlert.objects.get_or_create(
            user=request.user,
            student=student,
            alert_date=date.today()
        )
        messages.success(request, f'Alert for {student.id} dismissed.')
    except Student.DoesNotExist:
        messages.error(request, 'Student not found.')
    
    return redirect('teacher_dashboard')

@login_required
def dismiss_all_alerts(request):
    """Teacher dismisses ALL absence alerts for today at once."""
    from core.models import Student
    from core.services import fetch_students_from_existing_db
    from attendance.models import Attendance
    from notifications.models import DismissedAlert
    from datetime import date, timedelta
    
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
    
    dismissed_count = 0
    for student in class_students:
        recent_days = [today - timedelta(days=i) for i in range(3)]
        absences = 0
        for d in recent_days:
            if not Attendance.objects.filter(student=student, scan_date=d).exists():
                absences += 1
        if absences >= 3:
            _, created = DismissedAlert.objects.get_or_create(
                user=request.user,
                student=student,
                alert_date=today
            )
            if created:
                dismissed_count += 1
    
    messages.success(request, f'{dismissed_count} alert(s) dismissed!')
    return redirect('teacher_dashboard')



@login_required
def change_password_request(request):
    """Step 1: Send verification code to user's email."""
    if request.method == 'POST':
        user = request.user
        
        # Generate 6-digit code
        code = str(random.randint(100000, 999999))
        user.verification_code = code
        user.verification_code_expires = timezone.now() + timedelta(minutes=10)
        user.save()
        
        # Send email
        from core.email_service import send_password_change_code
        send_password_change_code(user.email, code)
        
        messages.success(request, f'Verification code sent to {user.email}')
        return redirect('change_password_verify')
    
    return render_mobile_or_desktop(request, 'users/change_password_request.html', 'mobile/change_password_request.html', {
        'user_email': request.user.email,
    })


@login_required
def change_password_verify(request):
    """Step 2: Verify code and change password."""
    user = request.user
    
    if request.method == 'POST':
        entered_code = request.POST.get('code', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if entered_code != user.verification_code:
            messages.error(request, 'Invalid verification code.')
            return redirect('change_password_verify')
        
        if user.verification_code_expires and timezone.now() > user.verification_code_expires:
            messages.error(request, 'Verification code has expired. Request a new one.')
            return redirect('change_password_request')
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('change_password_verify')
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return redirect('change_password_verify')
        
        user.set_password(new_password)
        user.verification_code = ''
        user.verification_code_expires = None
        user.save()
        
        from django.contrib.auth import login
        login(request, user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('dashboard')
    
    return render_mobile_or_desktop(request, 'users/change_password_verify.html', 'mobile/change_password_verify.html', {})


@login_required
def scanner_view(request):
    """Scanner page for gate staff and bursar."""
    return render_mobile_or_desktop(request, 'admin_dashboard/scanner.html', 'mobile/scanner.html')


@login_required
@reauth_required
def user_management(request):
    """Super Admin: Manage all users."""
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    users = User.objects.all().order_by('role', 'username')
    return render_mobile_or_desktop(request, 'users/list.html', 'mobile/users_list.html', {'users': users})


@login_required
def add_user(request):
    """Super Admin: Add new user."""
    if request.user.role not in ['super_admin', 'admin']:
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
        
        # Send credentials email
        if email:
            try:
                from core.email_service import send_staff_credentials_email
                school_name = 'Jinja Senior Secondary School'
                login_url = request.build_absolute_uri('/login/')
                
                send_staff_credentials_email(
                    to_email=email,
                    username=username,
                    password=password,
                    full_name=f"{first_name} {last_name}".strip() or username,
                    role=dict(User.ROLE_CHOICES).get(role, role),
                    school_name=school_name,
                    login_url=login_url,
                )
            except Exception as e:
                logger.warning(f"Failed to send credentials email: {e}")
        
        messages.success(request, f'User "{username}" created successfully! Email sent to {email}.')
        return redirect('user_management')
    
    return render_mobile_or_desktop(request, 'users/form.html', 'mobile/users_form.html', {
        'edit_mode': False,
        'target_user': None,
        'is_own_profile': False,
    })


@login_required
def edit_user(request, user_id):
    """Super Admin: Edit existing user. Users can also edit their own profile."""
    target_user = get_object_or_404(User, id=user_id)
    
    # Allow users to edit their own profile, or super_admin to edit anyone
    if request.user.role != 'super_admin' and request.user.id != target_user.id:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        target_user.username = request.POST.get('username', target_user.username)
        target_user.email = request.POST.get('email', '')
        target_user.first_name = request.POST.get('first_name', '')
        target_user.last_name = request.POST.get('last_name', '')
        
        # Only super_admin can change role and assignments
        if request.user.role == 'super_admin':
            target_user.role = request.POST.get('role', target_user.role)
            target_user.assigned_location = request.POST.get('assigned_location', '')
            target_user.assigned_class = request.POST.get('assigned_class', '')
            target_user.assigned_stream = request.POST.get('assigned_stream', '')
        
        # Handle profile photo upload
        if 'profile_photo' in request.FILES:
            target_user.profile_photo = request.FILES['profile_photo']
        
        new_password = request.POST.get('password')
        if new_password:
            target_user.set_password(new_password)
        target_user.save()
        messages.success(request, f'Profile updated!')
        
        if request.user.role == 'super_admin':
            return redirect('user_management')
        return redirect('dashboard')
    
    return render_mobile_or_desktop(request, 'users/form.html', 'mobile/users_form.html', {
        'edit_mode': True,
        'target_user': target_user,
        'is_own_profile': request.user.id == target_user.id,
    })

@login_required
@reauth_required
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

@login_required
@reauth_required
def reset_system_data(request):
    """Super Admin: FULL system reset — deletes everything except Super Admin users."""
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        from core.models import Student
        from attendance.models import Attendance, MealLog, MealViolation, MealAccessRule, MealTimeSettings
        from movement.models import MovementLog
        from notifications.models import Notification, NotificationSetting, DismissedAlert, TeacherNotificationSetting
        from messaging.models import Message, Conversation
        from fees.models import FeeStructure
        from cards.models import CardTemplate
        
        counts = {}
        
        # Operational data
        counts['attendance'] = Attendance.objects.all().count()
        Attendance.objects.all().delete()
        
        counts['meal_logs'] = MealLog.objects.all().count()
        MealLog.objects.all().delete()
        
        counts['meal_violations'] = MealViolation.objects.all().count()
        MealViolation.objects.all().delete()
        
        counts['movement'] = MovementLog.objects.all().count()
        MovementLog.objects.all().delete()
        
        counts['notifications'] = Notification.objects.all().count()
        Notification.objects.all().delete()
        
        counts['dismissed'] = DismissedAlert.objects.all().count()
        DismissedAlert.objects.all().delete()
        
        counts['messages'] = Message.objects.all().count()
        Message.objects.all().delete()
        
        counts['conversations'] = Conversation.objects.all().count()
        Conversation.objects.all().delete()
        
        # Students & imports
        counts['students'] = Student.objects.all().count()
        Student.objects.all().delete()
        
        # Cards
        counts['card_templates'] = CardTemplate.objects.all().count()
        CardTemplate.objects.all().delete()
        
        # Fees & Meal config
        counts['fee_structures'] = FeeStructure.objects.all().count()
        FeeStructure.objects.all().delete()
        
        counts['meal_access_rules'] = MealAccessRule.objects.all().count()
        MealAccessRule.objects.all().delete()
        
        counts['meal_time_settings'] = MealTimeSettings.objects.all().count()
        MealTimeSettings.objects.all().delete()
        
        # Notification settings
        counts['notif_settings'] = NotificationSetting.objects.all().count()
        NotificationSetting.objects.all().delete()
        
        counts['teacher_notif'] = TeacherNotificationSetting.objects.all().count()
        TeacherNotificationSetting.objects.all().delete()
        
        # Delete all users EXCEPT super_admin
        from users.models import User
        non_super_users = User.objects.exclude(role='super_admin')
        counts['users'] = non_super_users.count()
        non_super_users.delete()
        
        total = sum(counts.values())
        logger.warning(f"FULL SYSTEM RESET by {request.user.username}. {total} records deleted!")
        messages.success(request, f'FULL SYSTEM RESET! {total} records deleted. Only Super Admin accounts remain.')
        
        return redirect('dashboard')
    
    # GET: Show confirmation page with counts
    from core.models import Student
    from attendance.models import Attendance, MealLog, MealViolation
    from movement.models import MovementLog
    from notifications.models import Notification
    from messaging.models import Message, Conversation
    from users.models import User
    
    preview = {
        'students': Student.objects.count(),
        'attendance': Attendance.objects.count(),
        'meal_logs': MealLog.objects.count(),
        'meal_violations': MealViolation.objects.count(),
        'movement': MovementLog.objects.count(),
        'messages': Message.objects.count(),
        'conversations': Conversation.objects.count(),
        'notifications': Notification.objects.count(),
        'users': User.objects.exclude(role='super_admin').count(),
    }
    preview['total'] = sum(preview.values())
    
    return render_mobile_or_desktop(request, 'users/reset_confirm.html', 'mobile/users_reset_confirm.html', {
        'preview': preview,
    })

from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def google_auth_receiver(request):
    """Receive Google auth data and log user in."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            
            from django.contrib.auth import login as django_login
            user = User.objects.get(email__iexact=email, is_active=True)
            django_login(request, user)
            messages.success(request, f'Welcome, {user.get_full_name() or user.username}!')
            return JsonResponse({'success': True, 'redirect': '/dashboard/'})
            
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'No staff account found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False}, status=405)