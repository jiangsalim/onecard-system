from django.db import models


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('IMPORT', 'Import'), ('SCAN', 'Scan'), ('PRINT', 'Print'),
        ('LOGIN', 'Login'), ('LOGOUT', 'Logout'), ('OTHER', 'Other'),
    ]

    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        ordering = ['-created_at']


class PromotionHistory(models.Model):
    ACTION_CHOICES = [('promoted', 'Promoted'), ('repeated', 'Repeated'), ('demoted', 'Demoted')]

    student = models.ForeignKey('core.Student', on_delete=models.CASCADE)
    from_class = models.CharField(max_length=20)
    to_class = models.CharField(max_length=20)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    academic_year = models.CharField(max_length=10)
    processed_by = models.CharField(max_length=50)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'promotion_history'
        ordering = ['-processed_at']