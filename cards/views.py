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

@login_required
def download_cards_pdf(request):
    """Open printable page for selected cards — front with badge/photo/QR, back with barcode."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    student_ids = request.GET.getlist('ids')
    if not student_ids:
        messages.error(request, 'No students selected.')
        return redirect('print_cards')
    
    students = Student.objects.filter(id__in=student_ids, status='active')
    
    from core.services import fetch_students_from_existing_db, generate_qr_for_student
    all_school = fetch_students_from_existing_db()
    school_dict = {s['admission_number']: s for s in all_school}
    
    template_map = {}
    for a in ClassTemplateAssignment.objects.filter(academic_year='2026').select_related('template'):
        if a.template:
            template_map[a.class_name] = a.template
    
    for s in students:
        if not s.qr_code:
            try:
                qr_file = generate_qr_for_student(s.id, version=s.card_version)
                s.qr_code.save(f'{s.id}.png', qr_file, save=True)
            except Exception:
                pass
    
    barcode_images = {}
    for s in students:
        try:
            barcode_data = f"{s.id}|{s.payment_code}"
            buffer = BytesIO()
            code128 = barcode.get('code128', barcode_data, writer=ImageWriter())
            code128.write(buffer)
            barcode_images[s.id] = base64.b64encode(buffer.getvalue()).decode()
        except Exception:
            barcode_images[s.id] = ''
    
    badge_url = 'https://res.cloudinary.com/lj8ucjmr/image/upload/v1784063633/onecard-jinja-sss/jinja-sss-badge.jpg'
    school_name = 'JINJA SENIOR SECONDARY SCHOOL'
    school_address = 'P.O Box 255, Jinja'
    school_phone = 'Tel: 0772404055'
    
    html = f"""<!DOCTYPE html>
    <html><head>
    <meta charset="utf-8">
    <link rel="icon" type="image/x-icon" href="https://res.cloudinary.com/lj8ucjmr/image/upload/v1784063633/onecard-jinja-sss/jinja-sss-badge.jpg">
    <title>OneCard Print</title>
    <style>
        @page {{ size: 320px 220px; margin: 0; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #e5e7eb; }}
        
        .toolbar {{
            text-align: center; padding: 16px;
            background: white; border-bottom: 1px solid #e5e7eb;
            position: sticky; top: 0; z-index: 10;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        .btn {{
            display: inline-flex; align-items: center; gap: 6px;
            padding: 10px 20px; border: none; border-radius: 10px;
            cursor: pointer; font-size: 13px; font-weight: 600;
            text-decoration: none; font-family: inherit;
            transition: all 0.15s ease; margin: 4px;
        }}
        .btn:hover {{ transform: translateY(-1px); }}
        .btn-print {{ background: #0A1F3F; color: white; }}
        .btn-print:hover {{ background: #132D52; box-shadow: 0 4px 12px rgba(10,31,63,0.25); }}
        .btn-close {{ background: #dc2626; color: white; }}
        .btn-close:hover {{ box-shadow: 0 4px 12px rgba(220,38,38,0.3); }}
        .card-count {{
            color: #6b7280; font-size: 12px; margin-top: 8px;
        }}
        
        .card, .card-back {{
            width: 300px; height: 200px; margin: 20px auto;
            border: 3px solid #0A1F3F; border-radius: 10px;
            background: white; page-break-after: always;
            page-break-inside: avoid; overflow: hidden;
        }}
        .card {{
            padding: 10px 12px; display: flex;
            flex-direction: column; justify-content: space-between;
        }}
        .card .top {{
            display: flex; align-items: center; gap: 8px;
            border-bottom: 1.5px solid #0A1F3F; padding-bottom: 5px;
        }}
        .card .top .badge img {{
            width: 42px; height: auto; max-height: 38px;
            border-radius: 6px; object-fit: contain;
        }}
        .card .top .school {{ font-weight: 700; font-size: 9px; color: #0A1F3F; }}
        .card .top .label {{ font-size: 7px; color: #6b7280; }}
        .card .top .badge-text {{
            font-size: 7px; padding: 2px 6px; border-radius: 4px;
            color: white; white-space: nowrap; font-weight: 600;
        }}
        .card .top .category-badge {{
            font-size: 7px; padding: 2px 6px; border-radius: 4px;
            color: white; white-space: nowrap; font-weight: 600; margin-left: 2px;
        }}
        .card .middle {{
            display: flex; align-items: center; gap: 6px;
            flex: 1; margin: 5px 0;
        }}
        .card .middle .photo-box {{
            width: 55px; height: 70px; flex-shrink: 0;
            border: 1.5px solid #e5e7eb; border-radius: 6px;
            overflow: hidden;
        }}
        .card .middle .photo-box img {{ width: 55px; height: 70px; object-fit: cover; }}
        .card .middle .qr {{ width: 62px; height: 62px; flex-shrink: 0; }}
        .card .middle .qr img {{ width: 62px; height: 62px; }}
        .card .middle .details {{
            font-size: 8px; line-height: 1.35; flex: 1;
        }}
        .card .middle .details strong {{ color: #0A1F3F; }}
        .card .bottom {{
            text-align: center; font-size: 6px; color: #9ca3af;
            border-top: 1px solid #e5e7eb; padding-top: 3px;
        }}
        
        .card-back {{
            padding: 12px 14px; display: flex;
            flex-direction: column; justify-content: space-between;
        }}
        .card-back .school-name {{
            font-size: 11px; font-weight: 700; text-align: center;
            border-bottom: 2px solid #0A1F3F; padding-bottom: 5px;
            margin-bottom: 6px; color: #0A1F3F;
        }}
        .card-back .info-section {{ font-size: 8px; line-height: 1.5; color: #374151; }}
        .card-back .info-section .row {{
            display: flex; justify-content: space-between; margin-bottom: 1px;
        }}
        .card-back .info-section strong {{ color: #0A1F3F; }}
        .card-back .barcode-box {{ text-align: center; margin: 5px 0; }}
        .card-back .barcode-box img {{ width: 240px; height: 38px; }}
        .card-back .barcode-text {{
            text-align: center; font-size: 7px; color: #6b7280;
            font-family: 'Courier New', monospace;
        }}
        .card-back .warning-box {{
            background: #fff7ed; border: 1px solid #fed7aa;
            border-radius: 6px; padding: 4px 6px;
            font-size: 7px; color: #ea580c; text-align: center;
            margin: 4px 0; font-weight: 600;
        }}
        .card-back .contact {{
            font-size: 7px; color: #9ca3af; text-align: center;
        }}
        
        @media print {{
            body {{ margin: 0; padding: 0; background: white; }}
            .no-print {{ display: none !important; }}
        }}
    </style></head><body>
    <div class="toolbar no-print">
        <button class="btn btn-print" onclick="window.print()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,9 6,2 18,2 18,9"/><path d="M6 12H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
            Print / Save as PDF
        </button>
        <button class="btn btn-close" onclick="window.close()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            Close
        </button>
        <p class="card-count">Total: {len(students)} cards (Front + Back)</p>
    </div>
    """
    
    # FRONT SIDES
    for s in students:
        qr_url = request.build_absolute_uri(s.qr_code.url) if s.qr_code else ''
        school_info = school_dict.get(s.admission_number, {})
        name_front = school_info.get('full_name', 'Student')
        student_class = school_info.get('current_class', 'N/A')
        student_stream = school_info.get('stream', '')
        student_category = school_info.get('category', s.category if hasattr(s, 'category') else 'day')
        
        tmpl = template_map.get(student_class)
        border_color = tmpl.border_color if tmpl else '#0A1F3F'
        bg_color = tmpl.background_color if tmpl else '#FFFFFF'
        badge_txt = tmpl.badge_text if tmpl else "STUDENT"
        badge_clr = tmpl.badge_color if tmpl else '#0A1F3F'
        color_name = tmpl.color_name if tmpl else ''
        
        if student_category == 'hostel':
            cat_badge = 'HOSTEL'
            cat_bg = '#d97706'; cat_text = '#FFF'; cat_icon_text = '[H]'
            if not tmpl: border_color = '#d97706'; bg_color = '#FFFDE7'
        else:
            cat_badge = 'DAY'
            cat_bg = '#6b7280'; cat_text = '#FFF'; cat_icon_text = '[D]'
            if not tmpl: border_color = '#6b7280'; bg_color = '#FAFAFA'
        
        if s.photo:
            photo_url = request.build_absolute_uri(s.photo.url)
        else:
            school_photo = school_info.get('photo_path', '')
            if school_photo and school_photo.startswith('http'):
                photo_url = school_photo
            elif school_photo:
                photo_url = request.build_absolute_uri(settings.MEDIA_URL + school_photo)
            else:
                name_encoded = quote(name_front)
                photo_url = f"https://ui-avatars.com/api/?name={name_encoded}&size=150&background=0A1F3F&color=fff"
        
        html += f"""
        <div class="card" style="border-color: {border_color}; background: {bg_color};">
            <div class="top" style="border-bottom-color: {border_color};">
                <div class="badge"><img src="{badge_url}" alt="Badge"></div>
                <div style="flex:1;"><div class="school">{school_name}</div><div class="label">Student ID Card</div></div>
                <div class="badge-text" style="background:{badge_clr};">{badge_txt} {color_name}</div>
                <div class="category-badge" style="background:{cat_bg}; color:{cat_text};">{cat_icon_text} {cat_badge}</div>
            </div>
            <div class="middle">
                <div class="photo-box"><img src="{photo_url}" alt="Photo"></div>
                <div class="qr"><img src="{qr_url}" alt="QR"></div>
                <div class="details">
                    <strong>ID:</strong> {s.id}<br><strong>Name:</strong> {name_front}<br>
                    <strong>Adm:</strong> {s.admission_number}<br><strong>Level:</strong> {badge_txt} {color_name}<br>
                    <strong>Stream:</strong> {student_stream}<br><strong>Category:</strong> {cat_icon_text} {cat_badge}<br>
                    <strong>Pay:</strong> {s.payment_code}<br><strong>Ver:</strong> v{s.card_version}
                </div>
            </div>
            <div class="bottom">Property of {school_name}. Return if found.</div>
        </div>
        """
    
    # BACK SIDES
    for s in students:
        school_info = school_dict.get(s.admission_number, {})
        name = school_info.get('full_name', 'Student')
        student_class = school_info.get('current_class', 'N/A')
        student_stream = school_info.get('stream', '')
        student_category = school_info.get('category', s.category if hasattr(s, 'category') else 'day')
        
        tmpl = template_map.get(student_class)
        border_color = tmpl.border_color if tmpl else '#0A1F3F'
        bg_color = tmpl.background_color if tmpl else '#FFFFFF'
        badge_txt = tmpl.badge_text if tmpl else "STUDENT"
        color_name = tmpl.color_name if tmpl else ''
        
        if student_category == 'hostel':
            cat_badge = 'HOSTEL'; cat_icon_text = '[H]'; cat_bg = '#d97706'
            if not tmpl: border_color = '#d97706'; bg_color = '#FFFDE7'
        else:
            cat_badge = 'DAY SCHOLAR'; cat_icon_text = '[D]'; cat_bg = '#6b7280'
            if not tmpl: border_color = '#6b7280'; bg_color = '#FAFAFA'
        
        barcode_img = barcode_images.get(s.id, '')
        barcode_data = f"{s.id}|{s.payment_code}"
        
        html += f"""
        <div class="card-back" style="border-color: {border_color}; background: {bg_color};">
            <div class="school-name" style="color: {border_color}; border-bottom-color: {border_color};">{school_name}</div>
            <div class="info-section">
                <div class="row"><strong>Name:</strong> <span>{name}</span></div>
                <div class="row"><strong>Level:</strong> <span>{badge_txt} {color_name}</span></div>
                <div class="row"><strong>Stream:</strong> <span>{student_stream}</span></div>
                <div class="row"><strong>Category:</strong> <span style="background:{cat_bg}; color:white; padding:1px 6px; border-radius:4px; font-size:7px;">{cat_icon_text} {cat_badge}</span></div>
                <div class="row"><strong>Adm No:</strong> <span>{s.admission_number}</span></div>
                <div class="row"><strong>Card ID:</strong> <span>{s.id} (v{s.card_version})</span></div>
                <div class="row"><strong>Pay Code:</strong> <span>{s.payment_code}</span></div>
            </div>
            <div class="barcode-box"><img src="data:image/png;base64,{barcode_img}" alt="Barcode"></div>
            <div class="barcode-text">{barcode_data}</div>
            <div class="warning-box">CARRY AT ALL TIMES • REPORT LOSS IMMEDIATELY</div>
            <div class="contact">{school_address} | {school_phone}</div>
        </div>
        """
    
    html += """</body></html>"""
    return HttpResponse(html)

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