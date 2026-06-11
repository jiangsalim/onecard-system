from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from datetime import date
from core.models import Student
from attendance.models import Attendance
from movement.models import MovementLog
import openpyxl


@login_required
def attendance_report(request):
    """Attendance report with chart."""
    today = date.today()
    attendance_list = Attendance.objects.filter(scan_date=today).select_related('student')[:50]
    
    total = Student.objects.filter(status='active').count()
    present = Attendance.objects.filter(scan_date=today).count()
    absent = total - present
    
    stats = {
        'total': total,
        'present': present,
        'absent': absent,
        'late': 0,
        'rate': round((present / total * 100) if total > 0 else 0, 1),
    }
    
    return render(request, 'reports/attendance.html', {
        'attendance_list': attendance_list,
        'stats': stats,
    })


@login_required
def export_attendance(request):
    """Export attendance to Excel."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Report"
    
    # Headers
    ws.append(['Student ID', 'Admission #', 'Date', 'Time In', 'Location', 'Marked By'])
    
    # Data
    for a in Attendance.objects.select_related('student').all()[:500]:
        ws.append([a.student.id, a.student.admission_number, str(a.scan_date), str(a.time_in), a.scan_location, a.marked_by])
    
    # Style header
    from openpyxl.styles import Font, PatternFill
    header_fill = PatternFill(start_color='1a237e', end_color='1a237e', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=attendance_report_{date.today()}.xlsx'
    wb.save(response)
    return response


@login_required
def export_fees(request):
    """Export fee balances to Excel."""
    from core.services import get_payment_balance
    from fees.models import FeeStructure
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Fee Report"
    
    ws.append(['Student ID', 'Admission #', 'Payment Code', 'Total Fees', 'Paid', 'Balance', 'Status'])
    
    for s in Student.objects.filter(status='active')[:500]:
        paid = get_payment_balance(s.payment_code)
        fee = FeeStructure.objects.first()
        total = float(fee.total_fees) if fee else 800000
        balance = total - float(paid)
        status = 'CLEARED' if balance <= 0 else 'NOT CLEARED'
        ws.append([s.id, s.admission_number, s.payment_code, total, float(paid), balance, status])
    
    header_fill = PatternFill(start_color='1a237e', end_color='1a237e', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=fee_report_{date.today()}.xlsx'
    wb.save(response)
    return response


@login_required
def export_movement(request):
    """Export movement log to Excel."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Movement Log"
    
    ws.append(['Student ID', 'Date', 'Time Out', 'Time In', 'Reason', 'Authorized By', 'Status'])
    
    for m in MovementLog.objects.select_related('student').all()[:500]:
        status = 'Returned' if m.time_in else 'Still Outside'
        ws.append([m.student.id, str(m.exit_date), str(m.time_out), str(m.time_in or '--'), m.get_reason_display(), m.authorized_by, status])
    
    header_fill = PatternFill(start_color='1a237e', end_color='1a237e', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=movement_log_{date.today()}.xlsx'
    wb.save(response)
    return response