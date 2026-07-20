from django.apps import AppConfig
import os
import sys

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Only run on the actual server, not during collectstatic/migrate/check
        if 'gunicorn' not in sys.argv[0] and 'runserver' not in sys.argv[0]:
            return

        try:
            from django.contrib.sites.models import Site
            from allauth.socialaccount.models import SocialApp

            # Auto-create or update Site
            site, _ = Site.objects.get_or_create(
                domain='onecard-jinja-sss.onrender.com',
                defaults={'name': 'OneCard Jinja SSS'}
            )

            # Only create if none exist
            if SocialApp.objects.filter(provider='google').count() == 0:
                app = SocialApp.objects.create(
                    provider='google',
                    name='Google',
                    client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
                    secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
                )
                app.sites.add(site)
                print(f"✅ Google Social App created (ID:{app.id})")
            else:
                print(f"✅ Google Social App already exists")

        except Exception as e:
            print(f"⚠️ Auto-setup skipped: {e}")