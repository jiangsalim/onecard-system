from django.core.management.base import BaseCommand
from users.models import User
from core.email_service import send_daily_report_email
from core.daily_reports import generate_daily_report


class Command(BaseCommand):
    help = 'Send daily email reports to all staff'

    def handle(self, *args, **options):
        users = User.objects.filter(is_active=True).exclude(email='')
        sent = 0
        
        for user in users:
            try:
                report_html = generate_daily_report(user)
                if report_html:
                    send_daily_report_email(
                        user.email,
                        user.get_full_name() or user.username,
                        report_html
                    )
                    sent += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed for {user.username}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} daily reports'))