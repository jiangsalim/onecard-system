from django.db import models


class FeeStructure(models.Model):
    class_name = models.CharField(max_length=20)
    term = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=10)
    total_fees = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fees_structure'
        unique_together = ['class_name', 'term', 'academic_year']
        ordering = ['academic_year', 'term', 'class_name']

    def __str__(self):
        return f"{self.class_name} - {self.term} {self.academic_year}: {self.total_fees} UGX"