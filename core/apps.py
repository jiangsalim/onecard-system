from django.apps import AppConfig
import os

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        try:
            from django.contrib.sites.models import Site
            from allauth.socialaccount.models import SocialApp

            # Auto-create Site for allauth
            site, _ = Site.objects.get_or_create(
                id=1,
                defaults={
                    'domain': 'onecard-jinja-sss.onrender.com',
                    'name': 'OneCard Jinja SSS'
                }
            )

            # Auto-create Google Social App
            google_app, created = SocialApp.objects.get_or_create(
                provider='google',
                defaults={
                    'name': 'Google',
                    'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
                    'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
                }
            )

            # Link site to app
            google_app.sites.add(site)

            print(f"✅ Site and Google Social App ready (Created: {created})")

        except Exception as e:
            print(f"⚠️ Auto-setup skipped: {e}")