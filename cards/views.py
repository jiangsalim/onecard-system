from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CardTemplate, ClassTemplateAssignment
from core.models import Student


@login_required
def template_list(request):
    """List all card templates."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    templates = CardTemplate.objects.all()
    return render(request, 'cards/template_list.html', {'templates': templates})


@login_required
def template_create(request):
    """Create a new card template."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        template = CardTemplate(
            name=request.POST.get('name'),
            class_level=request.POST.get('class_level'),
            color_name=request.POST.get('color_name'),
            background_color=request.POST.get('background_color', '#FFFFFF'),
            border_color=request.POST.get('border_color', '#000000'),
            border_style=request.POST.get('border_style', 'solid'),
            badge_text=request.POST.get('badge_text', "O'LEVEL"),
            badge_color=request.POST.get('badge_color', '#000000'),
        )
        template.save()
        messages.success(request, f'Template "{template.name}" created!')
        return redirect('template_list')
    
    return render(request, 'cards/template_form.html')


@login_required
def template_edit(request, template_id):
    """Edit a card template."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    template = get_object_or_404(CardTemplate, id=template_id)
    
    if request.method == 'POST':
        template.name = request.POST.get('name')
        template.class_level = request.POST.get('class_level')
        template.color_name = request.POST.get('color_name')
        template.background_color = request.POST.get('background_color', '#FFFFFF')
        template.border_color = request.POST.get('border_color', '#000000')
        template.border_style = request.POST.get('border_style', 'solid')
        template.badge_text = request.POST.get('badge_text', "O'LEVEL")
        template.badge_color = request.POST.get('badge_color', '#000000')
        template.save()
        messages.success(request, f'Template "{template.name}" updated!')
        return redirect('template_list')
    
    return render(request, 'cards/template_form.html', {'template': template})


@login_required
def template_delete(request, template_id):
    """Delete a card template."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    template = get_object_or_404(CardTemplate, id=template_id)
    name = template.name
    template.delete()
    messages.success(request, f'Template "{name}" deleted.')
    return redirect('template_list')


@login_required
def assign_templates(request):
    """Assign templates to classes."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    templates = CardTemplate.objects.all()
    assignments = ClassTemplateAssignment.objects.all()
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    
    if request.method == 'POST':
        for class_name in classes:
            template_id = request.POST.get(f'template_{class_name}')
            if template_id:
                template = CardTemplate.objects.get(id=template_id)
                ClassTemplateAssignment.objects.update_or_create(
                    class_name=class_name,
                    academic_year='2026',
                    defaults={
                        'template': template,
                        'assigned_by': request.user.get_full_name() or request.user.username
                    }
                )
        messages.success(request, 'Template assignments saved!')
        return redirect('assign_templates')
    
    # Build current assignments dict
    current = {a.class_name: a.template_id for a in assignments}
    
    return render(request, 'cards/assign_templates.html', {
        'templates': templates,
        'classes': classes,
        'current': current,
    })


@login_required
def print_cards(request):
    """Print cards for selected classes."""
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    classes = ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    
    if request.method == 'POST':
        selected_classes = request.POST.getlist('classes')
        students = Student.objects.filter(status='active')
        # In production, filter by class from existing DB
        return render(request, 'cards/print_preview.html', {
            'students': students,
            'selected_classes': selected_classes,
        })
    
    return render(request, 'cards/print_cards.html', {'classes': classes})