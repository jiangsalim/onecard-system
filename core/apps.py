from django.apps import AppConfig
import os
import sys

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        if 'gunicorn' not in sys.argv[0] and 'runserver' not in sys.argv[0]:
            return

        try:
            from django.contrib.sites.models import Site
            from allauth.socialaccount.models import SocialApp

            # Create site if not exists
            site, _ = Site.objects.get_or_create(
                domain='onecard-jinja-sss.onrender.com',
                defaults={'name': 'OneCard Jinja SSS'}
            )

            # Create SocialApp if not exists
            app, created = SocialApp.objects.get_or_create(
                provider='google',
                defaults={
                    'name': 'Google',
                    'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
                    'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
                }
            )
            app.sites.add(site)
            
            if created:
                print(f"✅ Google Social App created (ID:{app.id})")
            else:
                print(f"✅ Site (ID:{site.id}) linked to Google App (ID:{app.id})")

        except Exception as e:
            print(f"⚠️ Auto-setup: {e}")