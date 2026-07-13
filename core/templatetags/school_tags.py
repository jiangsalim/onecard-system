from django import template
from core.services import fetch_students_from_existing_db

register = template.Library()

@register.simple_tag
def get_streams():
    """Get unique streams from the school database."""
    try:
        students = fetch_students_from_existing_db()
        streams = sorted(set(s['stream'] for s in students if s.get('stream')))
        return streams if streams else ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    except Exception:
        return ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

@register.simple_tag
def get_classes():
    """Get unique classes from the school database."""
    try:
        students = fetch_students_from_existing_db()
        classes = sorted(set(s['current_class'] for s in students if s.get('current_class')))
        return classes if classes else ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']
    except Exception:
        return ['Senior 1', 'Senior 2', 'Senior 3', 'Senior 4', 'Senior 5', 'Senior 6']