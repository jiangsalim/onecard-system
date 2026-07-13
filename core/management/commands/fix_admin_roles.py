from django.core.management.base import BaseCommand
from users.models import User

class Command(BaseCommand):
    help = 'Fix admin user roles'

    def handle(self, *args, **options):
        User.objects.filter(username='jaing').update(
            role='super_admin', is_superuser=True, is_staff=True
        )
        User.objects.filter(username='admin').update(
            role='admin', is_superuser=True, is_staff=True
        )
        self.stdout.write(self.style.SUCCESS('Roles fixed!'))