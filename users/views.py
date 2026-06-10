from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages


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
    role = request.user.role
    if role in ['super_admin', 'admin']:
        return render(request, 'admin_dashboard/home.html')
    elif role == 'bursar':
        return redirect('bursar_dashboard')
    elif role == 'gate_staff':
        return redirect('gate_dashboard')
    elif role == 'class_teacher':
        return redirect('teacher_dashboard')
    return render(request, 'admin_dashboard/home.html')


@login_required
def bursar_dashboard(request):
    return render(request, 'admin_dashboard/bursar.html')


@login_required
def gate_dashboard(request):
    return render(request, 'admin_dashboard/gate.html')


@login_required
def teacher_dashboard(request):
    return render(request, 'admin_dashboard/teacher.html')