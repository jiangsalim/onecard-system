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
            site, _ = Site.objects.get_or_create(
                domain='onecard-jinja-sss.onrender.com',
                defaults={'name': 'OneCard Jinja SSS'}
            )

            # Only create Google Social App if NONE exists
            existing = SocialApp.objects.filter(provider='google')
            if existing.count() == 0:
                app = SocialApp.objects.create(
                    provider='google',
                    name='Google',
                    client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
                    secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
                )
                app.sites.add(site)
                print(f"✅ Google Social App created")
            else:
                # Ensure existing app is linked to the site
                for app in existing:
                    app.sites.add(site)
                print(f"✅ Google Social App already exists ({existing.count()} found)")

            print(f"✅ Site (ID:{site.id}) ready")

        except Exception as e:
            print(f"⚠️ Auto-setup skipped: {e}")