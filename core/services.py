import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.db import connections
import logging

logger = logging.getLogger('onecard')


def generate_qr_for_student(student_id):
    """Generate QR code image for a student."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(student_id)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue(), name=f"{student_id}.png")


def fetch_students_from_existing_db():
    """Fetch active students from existing school database."""
    try:
        with connections['school_db'].cursor() as cursor:
            cursor.execute("""
                SELECT admission_number, full_name, payment_code, current_class, stream
                FROM students WHERE status = 'active'
            """)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to fetch from existing DB: {e}")
        return []


def get_student_info_from_existing_db(admission_number):
    """Fetch single student info from existing database."""
    try:
        with connections['school_db'].cursor() as cursor:
            cursor.execute("""
                SELECT full_name, current_class, stream, photo_path, status
                FROM students WHERE admission_number = %s
            """, [admission_number])
            row = cursor.fetchone()
            if row:
                return {
                    'name': row[0], 'class': row[1], 'stream': row[2],
                    'photo': row[3], 'status': row[4]
                }
    except Exception as e:
        logger.error(f"Failed to fetch student {admission_number}: {e}")
    return None


def get_payment_balance(payment_code):
    """Get total amount paid for a payment code."""
    try:
        with connections['school_db'].cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(amount_paid), 0) FROM payments
                WHERE payment_code = %s
            """, [payment_code])
            row = cursor.fetchone()
            return row[0] if row else 0
    except Exception as e:
        logger.error(f"Failed to get balance for {payment_code}: {e}")
        return 0


def get_next_student_id():
    """Generate next student ID (STU-001, STU-002, ...)."""
    from core.models import Student
    last = Student.objects.order_by('-id').first()
    if not last:
        return 'STU-001'
    num = int(last.id.replace('STU-', '')) + 1
    return f'STU-{num:03d}'