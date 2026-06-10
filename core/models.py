from django.db import models


class Student(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive')]

    id = models.CharField(max_length=20, primary_key=True)
    admission_number = models.CharField(max_length=30, unique=True)
    payment_code = models.CharField(max_length=50, unique=True)
    qr_code = models.ImageField(upload_to='qrcodes/', null=True, blank=True)
    template = models.ForeignKey('cards.CardTemplate', on_delete=models.SET_NULL, null=True, blank=True)
    card_printed = models.BooleanField(default=False)
    card_printed_date = models.DateField(null=True, blank=True)
    reprint_count = models.IntegerField(default=0)
    last_reprint_date = models.DateField(null=True, blank=True)
    last_reprint_reason = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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