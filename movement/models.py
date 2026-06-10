from django.db import models


class MovementLog(models.Model):
    REASON_CHOICES = [
        ('sick', 'Sick'), ('home', 'Home'),
        ('emergency', 'Emergency'), ('other', 'Other')
    ]

    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='movement_logs')
    exit_date = models.DateField()
    time_out = models.TimeField()
    time_in = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    authorized_by = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'movement_log'
        ordering = ['-exit_date', '-time_out']
        indexes = [
            models.Index(fields=['student', 'exit_date'], name='idx_mv_student_date'),
            models.Index(fields=['exit_date'], name='idx_mv_date'),
        ]

    def is_active(self):
        return self.time_in is None

    def __str__(self):
        status = "Outside" if self.is_active() else "Returned"
        return f"{self.student_id} - {self.exit_date} - {status}"