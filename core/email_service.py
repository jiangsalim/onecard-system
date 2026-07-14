"""
Email service using Brevo (Sendinblue) API with Herman Software branding.
"""
import logging
from django.conf import settings

logger = logging.getLogger('onecard')

# Herman Software Logo
HERMAN_LOGO_URL = 'https://res.cloudinary.com/lj8ucjmr/image/upload/v1784068502/onecard-branding/herman-logo.jpg'


def _send_brevo_email(to_email, to_name, subject, html_body):
    """Helper to send email via Brevo API."""
    api_key = getattr(settings, 'BREVO_API_KEY', '')
    
    if not api_key or api_key == 'your-brevo-api-key-here':
        return False
    
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
            to=[{"email": to_email, "name": to_name or to_email}],
            sender=sender,
            subject=subject,
            html_content=html_body,
        )
        
        api_instance.send_transac_email(send_smtp_email)
        return True
    except Exception as e:
        logger.error(f"Brevo error: {e}")
        return False


def send_password_change_code(to_email, code):
    """Send verification code for password change."""
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="{HERMAN_LOGO_URL}" alt="Herman Software" style="width: 50px; height: 50px; border-radius: 10px;">
        </div>
        <h2 style="color: #1a237e; text-align: center;">Password Change Request</h2>
        <p style="text-align: center;">You requested to change your password. Use this code:</p>
        <div style="background: #e8eaf6; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
            <h1 style="color: #1a237e; letter-spacing: 8px; font-size: 32px; margin: 0;">{code}</h1>
        </div>
        <p style="text-align: center;">This code expires in 10 minutes.</p>
        <p style="color: #666; text-align: center; font-size: 12px;">If you did not request this, ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <div style="text-align: center;">
            <img src="{HERMAN_LOGO_URL}" alt="Herman Software" style="width: 24px; height: 24px; border-radius: 4px; vertical-align: middle; margin-right: 6px;">
            <span style="color: #888; font-size: 11px;">Herman Software Solutions</span>
        </div>
    </div>
    """
    
    sent = _send_brevo_email(to_email, None, "Your OneCard Password Change Code", html_content)
    if not sent:
        print(f"\n  PASSWORD CHANGE CODE: {code} → {to_email}\n")
    return True


def send_staff_credentials_email(to_email, username, password, full_name, role, school_name, login_url):
    """Send login credentials to newly created staff."""
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="{HERMAN_LOGO_URL}" alt="Herman Software" style="width: 50px; height: 50px; border-radius: 10px;">
        </div>
        <h2 style="color: #1a237e; text-align: center;">Welcome to OneCard!</h2>
        <p style="text-align: center;">Hello {full_name},</p>
        <p style="text-align: center;">Your account has been created for <strong>{school_name}</strong>.</p>
        
        <div style="background: #e8eaf6; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Login Details:</strong></p>
            <p>Username: <strong>{username}</strong></p>
            <p>Password: <strong>{password}</strong></p>
            <p>Role: <strong>{role}</strong></p>
        </div>
        
        <div style="text-align: center;">
            <a href="{login_url}" style="display: inline-block; background: #1a237e; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">Login to OneCard</a>
        </div>
        
        <p style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">Please change your password after logging in for the first time.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <div style="text-align: center;">
            <img src="{HERMAN_LOGO_URL}" alt="Herman Software" style="width: 24px; height: 24px; border-radius: 4px; vertical-align: middle; margin-right: 6px;">
            <span style="color: #888; font-size: 11px;">Herman Software Solutions</span>
        </div>
    </div>
    """
    
    sent = _send_brevo_email(to_email, full_name, f"Your OneCard Account - {school_name}", html_content)
    if not sent:
        print(f"\n  NEW USER: {username} / {password} → {to_email}\n")
    return True


def send_daily_report_email(to_email, name, html_content):
    """Send daily report email with Herman branding."""
    
    # Wrap the report HTML with Herman branding
    branded_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 16px;">
            <img src="{HERMAN_LOGO_URL}" alt="Herman Software" style="width: 50px; height: 50px; border-radius: 10px;">
        </div>
        {html_content}
        <div style="text-align: center; padding: 16px; color: #888; font-size: 12px; border-top: 1px solid #eee; margin-top: 16px;">
            <img src="{HERMAN_LOGO_URL}" alt="Herman Software" style="width: 20px; height: 20px; border-radius: 4px; vertical-align: middle; margin-right: 4px;">
            Powered by Herman Software Solutions
        </div>
    </div>
    """
    
    sent = _send_brevo_email(to_email, name, f"OneCard Daily Report - {__import__('django').utils.timezone.now().strftime('%B %d, %Y')}", branded_html)
    if not sent:
        print(f"\n  DAILY REPORT → {to_email} (console fallback)\n")
    return True