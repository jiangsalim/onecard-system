from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
import os

class Command(BaseCommand):
    help = 'Setup Google OAuth Site and SocialApp'

    def handle(self, *args, **options):
        Site.objects.filter(domain='onecard-jinja-sss.onrender.com').delete()
        site = Site.objects.create(id=1, domain='onecard-jinja-sss.onrender.com', name='OneCard Jinja SSS')
        
        SocialApp.objects.filter(provider='google').delete()
        app = SocialApp.objects.create(
            provider='google', name='Google',
            client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
            secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        )
        app.sites.add(site)
        self.stdout.write(self.style.SUCCESS(f'Google OAuth ready! Site ID={site.id}'))