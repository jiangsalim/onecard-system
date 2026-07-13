from django.db import migrations

def fix_roles(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(username='jaing').update(
        role='super_admin', 
        is_superuser=True, 
        is_staff=True
    )
    User.objects.filter(username='admin').update(
        role='admin', 
        is_superuser=True, 
        is_staff=True
    )

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fix_roles),
    ]