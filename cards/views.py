from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from datetime import date
from .models import CardTemplate, ClassTemplateAssignment, CardReprint
from core.models import Student
from core.services import get_student_info_from_existing_db
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
    return render(request, 'cards/template_list.html', {'templates': templates})


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
    return render(request, 'cards/template_form.html')


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
    return render(request, 'cards/template_form.html', {'template': template})


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
    if request.method == 'POST':
        for class_name in classes:
            template_id = request.POST.get(f'template_{class_name}')
            if template_id:
                template = CardTemplate.objects.get(id=template_id)
                ClassTemplateAssignment.objects.update_or_create(
                    class_name=class_name, academic_year='2026',
                    defaults={'template': template, 'assigned_by': request.user.get_full_name() or request.user.username}
                )
        messages.success(request, 'Template assignments saved!')
        return redirect('assign_templates')
    assignments = ClassTemplateAssignment.objects.all()
    current = {a.class_name: a.template_id for a in assignments}
    return render(request, 'cards/assign_templates.html', {'templates': templates, 'classes': classes, 'current': current})


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
        elif action == 'print_selected':
            selected_ids = request.POST.getlist('selected_students')
            if selected_ids:
                Student.objects.filter(id__in=selected_ids).update(card_printed=True, card_printed_date=date.today())
                messages.success(request, f'{len(selected_ids)} card(s) marked as printed.')
            return redirect('print_cards')
    return render(request, 'cards/print_cards.html', {'classes': classes, 'students': students, 'selected_class': selected_class})


@login_required
def download_cards_pdf(request):
    """Open printable page for selected cards — front with badge/photo/QR, back with barcode. Uses assigned template colors and Day/Hostel category."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    student_ids = request.GET.getlist('ids')
    if not student_ids:
        messages.error(request, 'No students selected.')
        return redirect('print_cards')
    
    students = Student.objects.filter(id__in=student_ids, status='active')
    
    # Pre-fetch all student info from school DB
    from core.services import fetch_students_from_existing_db
    all_school = fetch_students_from_existing_db()
    school_dict = {s['admission_number']: s for s in all_school}
    
    # Pre-fetch template assignments for colors
    template_map = {}
    for a in ClassTemplateAssignment.objects.filter(academic_year='2026').select_related('template'):
        if a.template:
            template_map[a.class_name] = a.template
    
    # Pre-generate barcodes
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
    
    # School badge URL
    badge_url = request.build_absolute_uri('/media/badge.jpg')
    
    html = """<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>OneCard Print</title>
    <style>
        @page { size: 320px 220px; margin: 0; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: white; }
        
        .no-print-btn { 
            display: inline-block; background: #1a237e; color: white; padding: 10px 20px; 
            border: none; border-radius: 4px; cursor: pointer; font-size: 13px; margin: 5px; 
            text-decoration: none;
        }
        
        .card, .card-back {
            width: 300px; height: 200px; margin: 0 auto;
            border: 3px solid #1a237e; border-radius: 6px;
            background: white; page-break-after: always; 
            page-break-inside: avoid; overflow: hidden;
        }
        
        /* FRONT */
        .card {
            padding: 8px 10px;
            display: flex; flex-direction: column; justify-content: space-between;
        }
        .card .top { 
            display: flex; align-items: center; gap: 8px; 
            border-bottom: 1px solid #1a237e; padding-bottom: 4px;
        }
        .card .top .badge img { width: 45px; height: auto; max-height: 40px; border-radius: 4px; object-fit: contain; }
        .card .top .school { font-weight: bold; font-size: 9px; color: #1a237e; }
        .card .top .label { font-size: 7px; color: #888; }
        .card .top .badge-text { font-size: 7px; padding: 2px 6px; border-radius: 3px; color: white; white-space: nowrap; }
        .card .top .category-badge { font-size: 7px; padding: 2px 6px; border-radius: 3px; color: white; white-space: nowrap; margin-left: 2px; }
        .card .middle { 
            display: flex; align-items: center; gap: 6px; flex: 1; margin: 4px 0; 
        }
        .card .middle .photo-box { width: 55px; height: 70px; flex-shrink: 0; border: 1px solid #ddd; }
        .card .middle .photo-box img { width: 55px; height: 70px; object-fit: cover; }
        .card .middle .qr { width: 65px; height: 65px; flex-shrink: 0; }
        .card .middle .qr img { width: 65px; height: 65px; }
        .card .middle .details { font-size: 8px; line-height: 1.3; flex: 1; }
        .card .middle .details strong { color: #1a237e; }
        .card .bottom { text-align: center; font-size: 6px; color: #888; border-top: 1px solid #ddd; padding-top: 2px; }
        
        /* BACK */
        .card-back {
            padding: 10px 14px;
            display: flex; flex-direction: column; justify-content: space-between;
        }
        .card-back .school-name { font-size: 10px; font-weight: bold; text-align: center; border-bottom: 2px solid #1a237e; padding-bottom: 4px; margin-bottom: 4px; }
        .card-back .info-section { font-size: 8px; line-height: 1.4; color: #333; }
        .card-back .info-section .row { display: flex; justify-content: space-between; margin-bottom: 1px; }
        .card-back .info-section strong { color: #1a237e; }
        .card-back .barcode-box { text-align: center; margin: 4px 0; }
        .card-back .barcode-box img { width: 250px; height: 40px; }
        .card-back .barcode-text { text-align: center; font-size: 7px; color: #666; font-family: 'Courier New', monospace; }
        .card-back .warning-box { background: #fff3e0; border: 1px solid #ffcc80; border-radius: 4px; padding: 4px 6px; font-size: 7px; color: #e65100; text-align: center; margin: 3px 0; }
        .card-back .contact { font-size: 7px; color: #666; text-align: center; }
        
        @media print {
            body { margin: 0; padding: 0; }
            .no-print { display: none !important; }
        }
    </style></head><body>
    <div style="text-align:center; padding:10px;" class="no-print">
        <button class="no-print-btn" onclick="window.print()">Print / Save as PDF</button>
        <button class="no-print-btn" onclick="window.close()" style="background:#c62828;">Close</button>
        <p style="color:#666; font-size:11px; margin:8px 0;">Total: """ + str(len(students)) + """ cards (Front + Back)</p>
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
        
        # Get assigned template colors
        tmpl = template_map.get(student_class)
        border_color = tmpl.border_color if tmpl else '#1a237e'
        bg_color = tmpl.background_color if tmpl else '#FFFFFF'
        badge_txt = tmpl.badge_text if tmpl else "STUDENT"
        badge_clr = tmpl.badge_color if tmpl else '#1a237e'
        color_name = tmpl.color_name if tmpl else ''
        
        # Category styling — if no template assigned, use category colors
        if student_category == 'hostel':
            cat_badge = 'HOSTEL'
            cat_bg = '#FF8F00'
            cat_text = '#FFF'
            cat_icon_text = '[H]'  # for hostel
            if not tmpl:
                border_color = '#FF8F00'
                bg_color = '#FFFDE7'
        else:
            cat_badge = 'DAY'
            cat_bg = '#78909C'
            cat_text = '#FFF'
            cat_icon_text = '[D]'  # for day scholar
            if not tmpl:
                border_color = '#78909C'
                bg_color = '#FAFAFA'
        
        # Photo URL — priority: 1) Admin uploaded  2) School DB photo_path  3) Generated avatar
        if s.photo:
            photo_url = request.build_absolute_uri(s.photo.url)
        else:
            school_photo = school_info.get('photo_path', '')
            if school_photo:
                photo_url = request.build_absolute_uri('/media/' + school_photo) if school_photo.startswith('/') else school_photo
            else:
                name_encoded = quote(name_front)
                photo_url = f"https://ui-avatars.com/api/?name={name_encoded}&size=150&background=1a237e&color=fff"
        
        html += f"""
        <div class="card" style="border-color: {border_color}; background: {bg_color};">
            <div class="top" style="border-bottom-color: {border_color};">
                <div class="badge"><img src="{badge_url}" alt="Badge"></div>
                <div style="flex:1;">
                    <div class="school">JINJA SENIOR SECONDARY SCHOOL</div>
                    <div class="label">Student ID Card</div>
                </div>
                <div class="badge-text" style="background:{badge_clr};">{badge_txt} {color_name}</div>
                <div class="category-badge" style="background:{cat_bg}; color:{cat_text};">{cat_icon_text} {cat_badge}</div>
            </div>
            <div class="middle">
                <div class="photo-box"><img src="{photo_url}" alt="Photo"></div>
                <div class="qr"><img src="{qr_url}" alt="QR"></div>
                <div class="details">
                    <strong>ID:</strong> {s.id}<br>
                    <strong>Name:</strong> {name_front}<br>
                    <strong>Adm:</strong> {s.admission_number}<br>
                    <strong>Level:</strong> {badge_txt} {color_name}<br>
                    <strong>Stream:</strong> {student_stream}<br>
                    <strong>Category:</strong> {cat_icon_text} {cat_badge}<br>
                    <strong>Pay:</strong> {s.payment_code}<br>
                    <strong>Ver:</strong> v{s.card_version}
                </div>
            </div>
            <div class="bottom">Property of JINJA SSS. Return if found.</div>
        </div>
        """
    
    # BACK SIDES
    for s in students:
        school_info = school_dict.get(s.admission_number, {})
        name = school_info.get('full_name', 'Student')
        student_class = school_info.get('current_class', 'N/A')
        student_stream = school_info.get('stream', '')
        student_category = school_info.get('category', s.category if hasattr(s, 'category') else 'day')
        
        # Get template colors
        tmpl = template_map.get(student_class)
        border_color = tmpl.border_color if tmpl else '#1a237e'
        bg_color = tmpl.background_color if tmpl else '#FFFFFF'
        badge_txt = tmpl.badge_text if tmpl else "STUDENT"
        badge_clr = tmpl.badge_color if tmpl else '#1a237e'
        color_name = tmpl.color_name if tmpl else ''
        
        # Category
        if student_category == 'hostel':
            cat_badge = 'HOSTEL'
            cat_icon_text = '[H]'  # for hostel
            cat_bg = '#FF8F00'
            if not tmpl:
                border_color = '#FF8F00'
                bg_color = '#FFFDE7'
        else:
            cat_badge = 'DAY SCHOLAR'
            cat_icon_text = '[D]'  # for day scholar
            cat_bg = '#78909C'
            if not tmpl:
                border_color = '#78909C'
                bg_color = '#FAFAFA'
        
        barcode_img = barcode_images.get(s.id, '')
        barcode_data = f"{s.id}|{s.payment_code}"
        
        html += f"""
        <div class="card-back" style="border-color: {border_color}; background: {bg_color};">
            <div class="school-name" style="color: {border_color}; border-bottom-color: {border_color};">JINJA SENIOR SECONDARY SCHOOL</div>
            <div class="info-section">
                <div class="row"><strong>Name:</strong> <span>{name}</span></div>
                <div class="row"><strong>Level:</strong> <span>{badge_txt} {color_name}</span></div>
                <div class="row"><strong>Stream:</strong> <span>{student_stream}</span></div>
                <div class="row"><strong>Category:</strong> <span style="background:{cat_bg}; color:white; padding:1px 6px; border-radius:3px; font-size:7px;">{cat_icon_text} {cat_badge}</span></div>
                <div class="row"><strong>Adm No:</strong> <span>{s.admission_number}</span></div>
                <div class="row"><strong>Card ID:</strong> <span>{s.id} (v{s.card_version})</span></div>
                <div class="row"><strong>Pay Code:</strong> <span>{s.payment_code}</span></div>
            </div>
            <div class="barcode-box"><img src="data:image/png;base64,{barcode_img}" alt="Barcode"></div>
            <div class="barcode-text">{barcode_data}</div>
            <div class="warning-box">CARRY AT ALL TIMES &bull; REPORT LOSS IMMEDIATELY</div>
            <div class="contact">P.O Box 255, Jinja | Tel: 0772404055</div>
        </div>
        """
    
    html += """</body></html>"""
    return HttpResponse(html)

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
    return render(request, 'cards/reprint.html', {'student': student, 'reprints': reprints})

@login_required
def printed_cards(request):
    """View all printed cards."""
    if request.user.role not in ['super_admin', 'admin', 'bursar']:
        messages.error(request, 'Access denied.'); return redirect('dashboard')
    
    students = Student.objects.filter(card_printed=True, status='active').select_related('template').order_by('-card_printed_date')
    
    return render(request, 'cards/printed_cards.html', {'students': students})