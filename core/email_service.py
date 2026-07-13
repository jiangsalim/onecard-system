def send_password_change_code(to_email, code):
    """Send verification code for password change."""
    import random
    from django.conf import settings
    
    api_key = getattr(settings, 'BREVO_API_KEY', '')
    
    if not api_key or api_key == 'your-brevo-api-key-here':
        print(f"\n  PASSWORD CHANGE CODE: {code} → {to_email}\n")
        return True
    
    try:
        import sib_api_v3_sdk
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        
        sender = {
            "email": settings.BREVO_SENDER_EMAIL,
            "name": settings.BREVO_SENDER_NAME
        }
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1a237e;">Password Change Request</h2>
            <p>You requested to change your password. Use this code:</p>
            <div style="background: #e8eaf6; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                <h1 style="color: #1a237e; letter-spacing: 8px; font-size: 32px; margin: 0;">{code}</h1>
            </div>
            <p>This code expires in 10 minutes.</p>
            <p style="color: #666;">If you did not request this, ignore this email.</p>
        </div>
        """
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            sender=sender,
            subject="Your OneCard Password Change Code",
            html_content=html_content,
        )
        
        api_instance.send_transac_email(send_smtp_email)
        return True
    except Exception as e:
        print(f"\n  PASSWORD CHANGE CODE: {code} → {to_email}\n")
        return True
    

def send_staff_credentials_email(to_email, username, password, full_name, role, school_name, login_url):
    """Send login credentials to newly created staff."""
    from django.conf import settings
    
    api_key = getattr(settings, 'BREVO_API_KEY', '')
    
    if not api_key or api_key == 'your-brevo-api-key-here':
        print(f"\n  NEW USER CREDENTIALS:")
        print(f"  Email: {to_email}")
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print(f"  Role: {role}")
        print(f"  Login: {login_url}\n")
        return True
    
    try:
        import sib_api_v3_sdk
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        
        sender = {
            "email": settings.BREVO_SENDER_EMAIL,
            "name": settings.BREVO_SENDER_NAME
        }
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1a237e;">Welcome to OneCard!</h2>
            <p>Hello {full_name},</p>
            <p>Your account has been created for <strong>{school_name}</strong>.</p>
            
            <div style="background: #e8eaf6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Login Details:</strong></p>
                <p>Username: <strong>{username}</strong></p>
                <p>Password: <strong>{password}</strong></p>
                <p>Role: <strong>{role}</strong></p>
            </div>
            
            <a href="{login_url}" style="display: inline-block; background: #1a237e; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">Login to OneCard</a>
            
            <p style="margin-top: 20px; color: #666;">Please change your password after logging in for the first time.</p>
        </div>
        """
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            sender=sender,
            subject=f"Your OneCard Account - {school_name}",
            html_content=html_content,
        )
        
        api_instance.send_transac_email(send_smtp_email)
        return True
    except Exception as e:
        print(f"\n  NEW USER: {username} / {password} → {to_email}\n")
        return True
    

def send_daily_report_email(to_email, name, html_content):
    """Send daily report email."""
    from django.conf import settings
    
    api_key = getattr(settings, 'BREVO_API_KEY', '')
    
    if not api_key or api_key == 'your-brevo-api-key-here':
        print(f"\n  DAILY REPORT → {to_email} (no API key)\n")
        return True
    
    try:
        import sib_api_v3_sdk
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        
        sender = {
            "email": settings.BREVO_SENDER_EMAIL,
            "name": settings.BREVO_SENDER_NAME
        }
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email, "name": name}],
            sender=sender,
            subject=f"OneCard Daily Report - {__import__('django').utils.timezone.now().strftime('%B %d, %Y')}",
            html_content=html_content,
        )
        
        api_instance.send_transac_email(send_smtp_email)
        print(f"  Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"  DAILY REPORT ERROR: {e}")
        print(f"  DAILY REPORT → {to_email} (console fallback)\n")
        return True