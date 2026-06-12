from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess
from datetime import datetime


class Command(BaseCommand):
    help = 'Backup the database'

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = settings.BASE_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        filename = backup_dir / f'onecard_backup_{timestamp}.sql'
        
        # Full path to mysqldump on Windows
        cmd = [
            r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe',
            f'--user={db["USER"]}',
            f'--password={db["PASSWORD"]}',
            f'--host={db["HOST"]}',
            f'--port={db["PORT"]}',
            '--skip-column-statistics',
            db['NAME'],
        ]
        
        try:
            with open(filename, 'w') as f:
                subprocess.run(cmd, stdout=f, check=True, stderr=subprocess.PIPE)
            file_size = filename.stat().st_size
            self.stdout.write(self.style.SUCCESS(f'Backup saved: {filename.name} ({file_size:,} bytes)'))
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f'Backup failed: {e.stderr.decode()}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Backup failed: {e}'))