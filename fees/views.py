from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import FeeStructure
from core.mobile_utils import render_mobile_or_desktop
from django.utils import timezone


@login_required
def fee_management(request):
    """Manage fee structures — Day and Hostel separately."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    term = request.POST.get('term', 'Term 2')
    year = request.POST.get('academic_year', '2026')
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    categories = ['day', 'hostel']
    
    existing_fees = {}
    for f in FeeStructure.objects.filter(term=term, academic_year=year):
        key = f"{f.class_name}_{f.category}"
        existing_fees[key] = f.total_fees
    
    if request.method == 'POST' and request.POST.get('action') == 'save':
        for class_name in classes:
            for cat in categories:
                amount = request.POST.get(f'fees_{class_name}_{cat}')
                if amount:
                    FeeStructure.objects.update_or_create(
                        class_name=class_name, category=cat, term=term, academic_year=year,
                        defaults={'total_fees': amount}
                    )
                    existing_fees[f"{class_name}_{cat}"] = amount
        messages.success(request, f'Fees updated for {term} {year}!')
    
    return render_mobile_or_desktop(request, 'fees/management.html', 'mobile/fees_management.html', {
        'classes': classes, 'categories': categories, 'term': term, 'year': year, 'existing_fees': existing_fees,
    })
from django.core.cache import cache
from core.cache_utils import get_or_set, make_key

@login_required
def fee_report(request):
    """View fee balances with caching."""
    if request.user.role not in ['super_admin', 'admin', 'bursar', 'class_teacher']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    from core.models import Student
    from core.services import get_payment_balance, get_student_info_from_existing_db, fetch_students_from_existing_db
    
    status_filter = request.GET.get('status', 'all')
    class_filter = request.GET.get('class', '')
    stream_filter = request.GET.get('stream', '')
    search_query = request.GET.get('search', '').strip()
    
    if request.user.role == 'class_teacher':
        class_filter = request.user.assigned_class
        stream_filter = request.user.assigned_stream
    
    has_filter = bool(class_filter or stream_filter or search_query or status_filter != 'all')
    
    # Cache only unfiltered full report
    if not has_filter:
        cache_key = make_key('fee_report')
        cached = cache.get(cache_key)
        if cached:
            return render_mobile_or_desktop(request, 'fees/report.html', 'mobile/fees_report.html', cached)
    
    if class_filter:
        all_school = fetch_students_from_existing_db()
        matching_admissions = [
            s['admission_number'] for s in all_school 
            if s['current_class'] == class_filter 
            and (not stream_filter or s['stream'] == stream_filter)
        ]
        students = Student.objects.filter(admission_number__in=matching_admissions, status='active')
    else:
        students = Student.objects.filter(status='active')
    
    # Cache fee map
    fee_map = get_or_set(
        make_key('fee_map'),
        lambda: {f"{f.class_name}_{f.category}": float(f.total_fees) for f in FeeStructure.objects.filter(term='Term 2', academic_year='2026')},
        timeout=600
    )
    
    student_data = []
    cleared_count = not_cleared_count = not_paid_count = 0
    
    for s in students:
        info = get_student_info_from_existing_db(s.admission_number)
        if not info:
            continue
        
        class_name = info.get('class', '')
        student_stream = info.get('stream', '')
        student_category = s.category if hasattr(s, 'category') else 'day'
        
        if search_query and search_query.lower() not in info.get('name', '').lower() and search_query.lower() not in s.admission_number.lower():
            continue
        
        paid = get_payment_balance(s.payment_code)
        fee_key = f"{class_name}_{student_category}"
        total_fee = fee_map.get(fee_key, 800000)
        balance = total_fee - float(paid)
        
        if balance <= 0 and float(paid) > 0:
            status = 'CLEARED'; cleared_count += 1
        elif float(paid) == 0:
            status = 'NOT PAID'; not_paid_count += 1
        else:
            status = 'NOT CLEARED'; not_cleared_count += 1
        
        if status_filter != 'all' and status.lower().replace(' ', '_') != status_filter:
            continue
        
        student_data.append({
            'id': s.id, 'admission': s.admission_number, 'payment_code': s.payment_code,
            'name': info.get('name', ''), 'class': class_name, 'stream': student_stream,
            'category': student_category, 'total': total_fee, 'paid': float(paid),
            'balance': balance, 'status': status,
        })
    
    classes = get_or_set(
        make_key('class_list'),
        lambda: ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6'],
        timeout=600
    )
    
    context = {
        'students': student_data, 'classes': classes, 'status_filter': status_filter,
        'class_filter': class_filter, 'stream_filter': stream_filter, 'search_query': search_query,
        'cleared_count': cleared_count, 'not_cleared_count': not_cleared_count,
        'not_paid_count': not_paid_count, 'total_count': len(student_data),
    }
    
    # Cache unfiltered report for 5 minutes
    if not has_filter:
        cache.set(make_key('fee_report'), context, 300)
    
    return render_mobile_or_desktop(request, 'fees/report.html', 'mobile/fees_report.html', context)

@login_required
def meal_access_rules(request):
    """Manage meal access rules — max balance per class/category."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    from attendance.models import MealAccessRule
    
    term = request.POST.get('term', 'Term 2')
    year = request.POST.get('academic_year', '2026')
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    categories = ['day', 'hostel']
    
    existing_rules = {}
    for r in MealAccessRule.objects.filter(term=term, academic_year=year):
        key = f"{r.class_name}_{r.category}"
        existing_rules[key] = r.max_balance
    
    if request.method == 'POST' and request.POST.get('action') == 'save':
        for class_name in classes:
            for cat in categories:
                amount = request.POST.get(f'rule_{class_name}_{cat}')
                if amount:
                    MealAccessRule.objects.update_or_create(
                        class_name=class_name, category=cat, term=term, academic_year=year,
                        defaults={'max_balance': amount}
                    )
                    existing_rules[f"{class_name}_{cat}"] = amount
        messages.success(request, f'Meal access rules updated for {term} {year}!')
    
    return render_mobile_or_desktop(request, 'fees/meal_rules.html', 'mobile/fees_meal_rules.html', {
        'classes': classes, 'categories': categories, 'term': term, 'year': year, 'existing_rules': existing_rules,
    })

@login_required
def meal_time_settings(request):
    """Manage meal time windows."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    from attendance.models import MealTimeSettings
    settings, _ = MealTimeSettings.objects.get_or_create(id=1)
    
    if request.method == 'POST':
        settings.breakfast_start = request.POST.get('breakfast_start', '07:00')
        settings.breakfast_end = request.POST.get('breakfast_end', '08:30')
        settings.lunch_start = request.POST.get('lunch_start', '12:30')
        settings.lunch_end = request.POST.get('lunch_end', '14:00')
        settings.supper_start = request.POST.get('supper_start', '18:00')
        settings.supper_end = request.POST.get('supper_end', '19:30')
        settings.save()
        messages.success(request, 'Meal times updated!')
    
    return render_mobile_or_desktop(request, 'fees/meal_times.html', 'mobile/meal_times.html', {'settings': settings})

@login_required
def meal_violations(request):
    """View and resolve meal violations."""
    from attendance.models import MealViolation
    
    violations = MealViolation.objects.filter(resolved=False).select_related('student').order_by('-occurred_at')
    resolved = MealViolation.objects.filter(resolved=True).select_related('student').order_by('-resolved_at')[:20]
    
    return render_mobile_or_desktop(request, 'fees/meal_violations.html', 'mobile/fees_meal_violations.html', {
        'violations': violations,
        'resolved': resolved,
        'unresolved_count': violations.count(),
    })


@login_required
def resolve_violation(request, violation_id):
    """Mark a meal violation as resolved."""
    from attendance.models import MealViolation
    
    try:
        violation = MealViolation.objects.get(id=violation_id)
        violation.resolved = True
        violation.resolved_by = request.user.get_full_name() or request.user.username
        violation.resolved_at = timezone.now()
        violation.save()
        messages.success(request, f'Violation #{violation_id} resolved.')
    except MealViolation.DoesNotExist:
        messages.error(request, 'Violation not found.')
    
    return redirect('meal_violations')


@login_required
def resolve_all_violations(request):
    """Resolve all meal violations at once."""
    from attendance.models import MealViolation
    
    count = MealViolation.objects.filter(resolved=False).count()
    MealViolation.objects.filter(resolved=False).update(
        resolved=True,
        resolved_by=request.user.get_full_name() or request.user.username,
        resolved_at=timezone.now()
    )
    messages.success(request, f'{count} violation(s) resolved!')
    return redirect('meal_violations')