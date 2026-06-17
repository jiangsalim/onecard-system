from django.db import models
from django.conf import settings


class Notification(models.Model):
    PRIORITY_CHOICES = [('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]
    CATEGORY_CHOICES = [
        ('fee', 'Fees'), ('attendance', 'Attendance'),
        ('movement', 'Movement'), ('system', 'System')
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    related_student = models.ForeignKey('core.Student', on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']


class NotificationSetting(models.Model):
    """Global notification settings (admin-configurable)."""
    fee_balance_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=500000)
    fee_zero_payment_week = models.IntegerField(default=4)
    attendance_consecutive_days = models.IntegerField(default=3)
    attendance_weekly_days = models.IntegerField(default=5)
    attendance_term_percentage = models.IntegerField(default=75)
    movement_hours_outside = models.IntegerField(default=3)
    movement_exits_per_day = models.IntegerField(default=3)
    show_in_dashboard = models.BooleanField(default=True)
    email_alerts = models.BooleanField(default=False)
    email_recipient = models.EmailField(null=True, blank=True)
    late_cutoff_time = models.TimeField(default='08:00', help_text='Students arriving after this time are marked Late')

    class Meta:
        db_table = 'notification_settings'


class TeacherNotificationSetting(models.Model):
    """Per-teacher notification preferences."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_notif_settings'
    )
    alert_3_consecutive_absences = models.BooleanField(
        default=True,
        help_text='Alert when a student is absent 3+ consecutive days'
    )
    alert_attendance_below_75 = models.BooleanField(
        default=True,
        help_text='Alert when class attendance drops below 75%'
    )
    alert_5_absences_term = models.BooleanField(
        default=True,
        help_text='Alert when a student has 5+ absences this term'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_notification_settings'

    def __str__(self):
        return f"Notification Prefs — {self.user.get_full_name() or self.user.username}"

class DismissedAlert(models.Model):
    """Track which absence alerts a teacher has dismissed."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE)
    alert_date = models.DateField()  # The date the alert was for
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dismissed_alerts'
        unique_together = ['user', 'student', 'alert_date']  # Can't dismiss same alert twice