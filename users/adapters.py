from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect
from django.contrib import messages

class StaffGoogleAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        # Check if email exists in our system
        email = sociallogin.account.extra_data.get('email', '')
        
        from users.models import User
        try:
            user = User.objects.get(email=email)
            # Email exists — link the Google account
            sociallogin.connect(request, user)
        except User.DoesNotExist:
            # No account with this email — reject
            messages.error(request, 'No staff account found with this email. Contact your administrator.')
            return redirect('login')