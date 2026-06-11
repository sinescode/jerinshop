from django.db import models

class HomeButton(models.Model):
    label = models.CharField(max_length=100)
    url = models.CharField(max_length=200)
    order = models.IntegerField(default=0, help_text="Lower number = appears first")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.label