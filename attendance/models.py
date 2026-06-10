from django.db import models


class ScanLocation(models.Model):
    MODE_CHOICES = [
        ('attendance_balance', 'Attendance + Balance'),
        ('balance_only', 'Balance Only'),
        ('pass_out', 'Pass Out / Return'),
        ('full_info', 'Full Info (No Log)'),
    ]

    location_name = models.CharField(max_length=50, unique=True)
    default_mode = models.CharField(max_length=30, choices=MODE_CHOICES, default='attendance_balance')
    status = models.CharField(max_length=10, default='active')

    class Meta:
        db_table = 'scan_locations'
        ordering = ['location_name']

    def __str__(self):
        return self.location_name


class Attendance(models.Model):
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='attendance_records')
    scan_date = models.DateField()
    time_in = models.TimeField()
    scan_location = models.CharField(max_length=50)
    marked_by = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attendance'
        ordering = ['-scan_date', '-time_in']
        unique_together = ['student', 'scan_date']
        indexes = [
            models.Index(fields=['student', 'scan_date'], name='idx_att_student_date'),
            models.Index(fields=['scan_date'], name='idx_att_date'),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.scan_date} - Present"