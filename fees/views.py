from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import FeeStructure


@login_required
def fee_management(request):
    """Manage fee structures."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    fees = FeeStructure.objects.all().order_by('academic_year', 'term', 'class_name')
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    
    if request.method == 'POST':
        term = request.POST.get('term', 'Term 2')
        year = request.POST.get('academic_year', '2026')
        
        for class_name in classes:
            amount = request.POST.get(f'fees_{class_name}')
            if amount:
                FeeStructure.objects.update_or_create(
                    class_name=class_name, term=term, academic_year=year,
                    defaults={'total_fees': amount}
                )
        messages.success(request, f'Fees updated for {term} {year}!')
        return redirect('fee_management')
    
    return render(request, 'fees/management.html', {
        'fees': fees,
        'classes': classes,
    })


@login_required
def fee_report(request):
    """View fee balances with real data from school database."""
    if request.user.role not in ['super_admin', 'admin', 'bursar']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    from core.models import Student
    from core.services import get_payment_balance, get_student_info_from_existing_db
    
    students = Student.objects.filter(status='active')
    student_data = []
    errors = 0
    
    for s in students[:50]:
        info = get_student_info_from_existing_db(s.admission_number)
        
        if not info:
            errors += 1
            continue
        
        class_name = info.get('class', '')
        paid = get_payment_balance(s.payment_code)
        fee = FeeStructure.objects.filter(class_name=class_name).first()
        
        if not fee:
            errors += 1
            continue
        
        total = float(fee.total_fees)
        balance = total - float(paid)
        
        if balance <= 0 and float(paid) > 0:
            status = 'CLEARED'
        elif float(paid) == 0:
            status = 'NOT PAID'
        else:
            status = 'NOT CLEARED'
        
        student_data.append({
            'id': s.id,
            'admission': s.admission_number,
            'payment_code': s.payment_code,
            'name': info.get('name', ''),
            'class': class_name,
            'total': total,
            'paid': float(paid),
            'balance': balance,
            'status': status,
        })
    
    if errors > 0:
        messages.warning(request, f'{errors} student(s) skipped — school database or fee structure missing.')
    
    return render(request, 'fees/report.html', {'students': student_data})