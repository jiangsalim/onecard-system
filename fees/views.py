from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import FeeStructure


@login_required
def fee_management(request):
    """Manage fee structures — shows saved fees, edit to change."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    term = request.POST.get('term', 'Term 2')
    year = request.POST.get('academic_year', '2026')
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    
    # Get existing fees
    existing_fees = {}
    for f in FeeStructure.objects.filter(term=term, academic_year=year):
        existing_fees[f.class_name] = f.total_fees
    
    if request.method == 'POST' and request.POST.get('action') == 'save':
        for class_name in classes:
            amount = request.POST.get(f'fees_{class_name}')
            if amount:
                FeeStructure.objects.update_or_create(
                    class_name=class_name, term=term, academic_year=year,
                    defaults={'total_fees': amount}
                )
                existing_fees[class_name] = amount
        messages.success(request, f'Fees updated for {term} {year}!')
    
    return render(request, 'fees/management.html', {
        'classes': classes,
        'term': term,
        'year': year,
        'existing_fees': existing_fees,
    })


@login_required
def fee_report(request):
    """View fee balances with filters."""
    if request.user.role not in ['super_admin', 'admin', 'bursar']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    from core.models import Student
    from core.services import get_payment_balance, get_student_info_from_existing_db
    
    # Get filter from URL
    status_filter = request.GET.get('status', 'all')  # all, cleared, not_cleared, not_paid
    class_filter = request.GET.get('class', '')
    search_query = request.GET.get('search', '').strip()
    
    students = Student.objects.filter(status='active')
    
    # Pre-fetch fee structures
    fee_map = {}
    for f in FeeStructure.objects.filter(term='Term 2', academic_year='2026'):
        fee_map[f.class_name] = float(f.total_fees)
    
    student_data = []
    cleared_count = 0
    not_cleared_count = 0
    not_paid_count = 0
    
    for s in students:
        info = get_student_info_from_existing_db(s.admission_number)
        if not info:
            continue
        
        class_name = info.get('class', '')
        
        # Class filter
        if class_filter and class_name != class_filter:
            continue
        
        # Search filter
        if search_query and search_query.lower() not in info.get('name', '').lower() and search_query.lower() not in s.admission_number.lower():
            continue
        
        paid = get_payment_balance(s.payment_code)
        total_fee = fee_map.get(class_name, 800000)
        balance = total_fee - float(paid)
        
        if balance <= 0 and float(paid) > 0:
            status = 'CLEARED'
            cleared_count += 1
        elif float(paid) == 0:
            status = 'NOT PAID'
            not_paid_count += 1
        else:
            status = 'NOT CLEARED'
            not_cleared_count += 1
        
                # Status filter — normalize: NOT PAID -> not_paid, NOT CLEARED -> not_cleared
        status_key = status.lower().replace(' ', '_')
        if status_filter != 'all' and status_key != status_filter:
            continue
        
        student_data.append({
            'id': s.id,
            'admission': s.admission_number,
            'payment_code': s.payment_code,
            'name': info.get('name', ''),
            'class': class_name,
            'stream': info.get('stream', ''),
            'total': total_fee,
            'paid': float(paid),
            'balance': balance,
            'status': status,
        })
    
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    
    return render(request, 'fees/report.html', {
        'students': student_data,
        'classes': classes,
        'status_filter': status_filter,
        'class_filter': class_filter,
        'search_query': search_query,
        'cleared_count': cleared_count,
        'not_cleared_count': not_cleared_count,
        'not_paid_count': not_paid_count,
        'total_count': len(student_data),
    })