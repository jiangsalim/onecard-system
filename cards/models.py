from django.db import models


class CardTemplate(models.Model):
    LEVEL_CHOICES = [('O', "O'LEVEL"), ('A', "A'LEVEL")]
    BORDER_STYLES = [('solid', 'Solid'), ('dashed', 'Dashed'), ('double', 'Double')]

    name = models.CharField(max_length=50)
    class_level = models.CharField(max_length=1, choices=LEVEL_CHOICES)
    color_name = models.CharField(max_length=30)
    background_color = models.CharField(max_length=7, default='#FFFFFF')
    border_color = models.CharField(max_length=7, default='#000000')
    border_style = models.CharField(max_length=20, choices=BORDER_STYLES, default='solid')
    accent_color = models.CharField(max_length=7, default='#000000')
    badge_text = models.CharField(max_length=20, default="O'LEVEL")
    badge_color = models.CharField(max_length=7, default='#000000')
    font_family = models.CharField(max_length=50, default='Arial')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'card_templates'
        ordering = ['class_level', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_class_level_display()})"


class ClassTemplateAssignment(models.Model):
    class_name = models.CharField(max_length=20)
    template = models.ForeignKey(CardTemplate, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=10)
    assigned_by = models.CharField(max_length=50)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'class_template_assignments'
        unique_together = ['class_name', 'academic_year']


class CardReprint(models.Model):
    REASON_CHOICES = [
        ('lost', 'Lost'), ('damaged', 'Damaged'),
        ('correction', 'Data Correction'), ('other', 'Other')
    ]

    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='reprints')
    reprint_number = models.IntegerField()
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes = models.TextField(null=True, blank=True)
    reprinted_by = models.CharField(max_length=50)
    reprinted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'card_reprints'
        ordering = ['-reprinted_at']