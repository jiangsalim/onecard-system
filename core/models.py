from django.db import models


class Student(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive')]

    id = models.CharField(max_length=20, primary_key=True)
    admission_number = models.CharField(max_length=30, unique=True)
    payment_code = models.CharField(max_length=50, unique=True)
    qr_code = models.ImageField(upload_to='qrcodes/', null=True, blank=True)
    photo = models.ImageField(upload_to='photos/', null=True, blank=True)
    template = models.ForeignKey('cards.CardTemplate', on_delete=models.SET_NULL, null=True, blank=True)
    card_printed = models.BooleanField(default=False)
    card_printed_date = models.DateField(null=True, blank=True)
    reprint_count = models.IntegerField(default=0)
    card_version = models.IntegerField(default=1)
    last_reprint_date = models.DateField(null=True, blank=True)
    last_reprint_reason = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    category = models.CharField(max_length=10, choices=[('day', 'Day Scholar'), ('hostel', 'Hostel Student')], default='day')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'students'
        ordering = ['admission_number']
        indexes = [
            models.Index(fields=['admission_number'], name='idx_admission_number'),
            models.Index(fields=['payment_code'], name='idx_payment_code'),
            models.Index(fields=['status'], name='idx_student_status'),
        ]

    def __str__(self):
        return f"{self.id} - {self.admission_number}"
    
class APIClient(models.Model):
    """External clients allowed to access public API (e.g., school website)."""
    name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=64, unique=True)
    allowed_ip = models.CharField(max_length=45, blank=True, help_text="IP address of the client server")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'api_clients'
    
    def __str__(self):
        return self.name