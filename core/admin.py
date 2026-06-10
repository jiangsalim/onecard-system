from django.contrib import admin
from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'admission_number', 'payment_code', 'status', 'card_printed')
    list_filter = ('status', 'card_printed')
    search_fields = ('id', 'admission_number', 'payment_code')