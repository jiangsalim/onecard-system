from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('bursar', 'Bursar'),
        ('gate_staff', 'Gate Staff'),
        ('class_teacher', 'Class Teacher'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='gate_staff')
    assigned_location = models.CharField(max_length=50, null=True, blank=True)
    assigned_class = models.CharField(max_length=20, null=True, blank=True)
    assigned_stream = models.CharField(max_length=20, null=True, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    groups = models.ManyToManyField(
        'auth.Group', verbose_name='groups', blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set', related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission', verbose_name='user permissions', blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set', related_query_name='custom_user',
    )

    class Meta:
        db_table = 'users'
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    def get_avatar_url(self):
        """Return profile photo URL or None for fallback to letter avatar."""
        if self.profile_photo:
            return self.profile_photo.url
        return None