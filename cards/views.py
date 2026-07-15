from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings
from datetime import date
from .models import CardTemplate, ClassTemplateAssignment, CardReprint
from core.models import Student
from core.services import get_student_info_from_existing_db
from core.mobile_utils import render_mobile_or_desktop
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import base64
from urllib.parse import quote


@login_required
def template_list(request):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    templates = CardTemplate.objects.all()
    return render_mobile_or_desktop(request, 'cards/template_list.html', 'mobile/cards_templates.html', {'templates': templates})


@login_required
def template_create(request):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    if request.method == 'POST':
        template = CardTemplate(
            name=request.POST.get('name'), class_level=request.POST.get('class_level'),
            color_name=request.POST.get('color_name'), background_color=request.POST.get('background_color', '#FFFFFF'),
            border_color=request.POST.get('border_color', '#000000'), border_style=request.POST.get('border_style', 'solid'),
            badge_text=request.POST.get('badge_text', "O'LEVEL"), badge_color=request.POST.get('badge_color', '#000000'),
        )
        template.save()
        messages.success(request, f'Template "{template.name}" created!')
        return redirect('template_list')
    return render_mobile_or_desktop(request, 'cards/template_form.html', 'mobile/cards_template_form.html')


@login_required
def template_edit(request, template_id):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    template = get_object_or_404(CardTemplate, id=template_id)
    if request.method == 'POST':
        template.name = request.POST.get('name'); template.class_level = request.POST.get('class_level')
        template.color_name = request.POST.get('color_name'); template.background_color = request.POST.get('background_color', '#FFFFFF')
        template.border_color = request.POST.get('border_color', '#000000'); template.border_style = request.POST.get('border_style', 'solid')
        template.badge_text = request.POST.get('badge_text', "O'LEVEL"); template.badge_color = request.POST.get('badge_color', '#000000')
        template.save()
        messages.success(request, f'Template "{template.name}" updated!')
        return redirect('template_list')
    return render_mobile_or_desktop(request, 'cards/template_form.html', 'mobile/cards_template_form.html', {'template': template})


@login_required
def template_delete(request, template_id):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    template = get_object_or_404(CardTemplate, id=template_id)
    name = template.name; template.delete()
    messages.success(request, f'Template "{name}" deleted.')
    return redirect('template_list')


@login_required
def assign_templates(request):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    templates = CardTemplate.objects.all()
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    assignments = ClassTemplateAssignment.objects.filter(academic_year='2026')
    current = {a.class_name: a.template_id for a in assignments}
    if request.method == 'POST':
        for class_name in classes:
            template_id = request.POST.get(f'template_{class_name}')
            if template_id:
                template = CardTemplate.objects.get(id=template_id)
                obj, created = ClassTemplateAssignment.objects.update_or_create(
                    class_name=class_name, academic_year='2026',
                    defaults={'template': template, 'assigned_by': request.user.get_full_name() or request.user.username}
                )
                current[class_name] = template_id
        messages.success(request, 'Template assignments saved!')
    return render_mobile_or_desktop(request, 'cards/assign_templates.html', 'mobile/cards_assign.html', {'templates': templates, 'classes': classes, 'current': current})


from core.services import generate_qr_base64

@login_required
def print_cards(request):
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    students = []; selected_class = ''
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'preview':
            selected_class = request.POST.get('class_name', '')
            if selected_class:
                from core.services import fetch_students_from_existing_db
                school_students = fetch_students_from_existing_db()
                class_admissions = [s['admission_number'] for s in school_students if s['current_class'] == selected_class]
                students = Student.objects.filter(admission_number__in=class_admissions, status='active', card_printed=False).select_related('template')
                # Add QR base64 for each student
                for s in students:
                    try:
                        s.qr_base64 = generate_qr_base64(s.id, s.card_version)
                    except Exception:
                        s.qr_base64 = ''
        elif action == 'print_selected':
            selected_ids = request.POST.getlist('selected_students')
            if selected_ids:
                Student.objects.filter(id__in=selected_ids).update(card_printed=True, card_printed_date=date.today())
                messages.success(request, f'{len(selected_ids)} card(s) marked as printed.')
            return redirect('print_cards')
    return render_mobile_or_desktop(request, 'cards/print_cards.html', 'mobile/cards_print.html', {'classes': classes, 'students': students, 'selected_class': selected_class})



@login_required
def reprint_card(request):
    if request.user.role not in ['super_admin', 'admin', 'bursar']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    student = None; reprints = []
    if request.method == 'POST':
        student_id = request.POST.get('student_id'); reason = request.POST.get('reason', 'lost')
        if student_id:
            try:
                student = Student.objects.get(id=student_id)
                reprints = CardReprint.objects.filter(student=student).order_by('-reprinted_at')
                if request.POST.get('confirm') == 'yes':
                    new_version = student.card_version + 1
                    CardReprint.objects.create(student=student, reprint_number=student.reprint_count + 1, reason=reason, reprinted_by=request.user.get_full_name() or request.user.username)
                    from core.services import generate_qr_for_student
                    new_qr = generate_qr_for_student(student.id, version=new_version)
                    student.reprint_count = student.reprint_count + 1
                    student.card_version = new_version
                    student.last_reprint_date = date.today()
                    student.last_reprint_reason = reason
                    student.card_printed = False
                    student.qr_code.save(f'{student.id}_v{new_version}.png', new_qr, save=False)
                    student.save()
                    messages.success(request, f'Reprint initiated! Card v{new_version} QR generated. Old card v{new_version - 1} is now invalid. Print the new card.')
                    return redirect('print_cards')
            except Student.DoesNotExist:
                messages.error(request, 'Student not found.')
    return render_mobile_or_desktop(request, 'cards/reprint.html', 'mobile/cards_reprint.html', {'student': student, 'reprints': reprints})


@login_required
def printed_cards(request):
    """View all printed cards."""
    if request.user.role not in ['super_admin', 'admin', 'bursar']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    students = Student.objects.filter(card_printed=True, status='active').select_related('template').order_by('-card_printed_date')
    return render_mobile_or_desktop(request, 'cards/printed_cards.html', 'mobile/cards_printed.html', {'students': students})