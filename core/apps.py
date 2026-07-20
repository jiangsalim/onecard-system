from django.apps import AppConfig
import os

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        try:
            from django.contrib.sites.models import Site
            from allauth.socialaccount.models import SocialApp

            # Auto-create or update Site
            site, created = Site.objects.get_or_create(
                domain='onecard-jinja-sss.onrender.com',
                defaults={
                    'name': 'OneCard Jinja SSS'
                }
            )
            if not created:
                site.name = 'OneCard Jinja SSS'
                site.save()

            # Auto-create Google Social App
            google_app, _ = SocialApp.objects.get_or_create(
                provider='google',
                defaults={
                    'name': 'Google',
                    'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
                    'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
                }
            )

            # Link site to app
            google_app.sites.add(site)

            print(f"✅ Site (ID:{site.id}) and Google Social App ready")

        except Exception as e:
            print(f"⚠️ Auto-setup skipped: {e}")