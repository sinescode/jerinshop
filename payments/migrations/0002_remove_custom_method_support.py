# Generated manually — interactive makemigrations failed on EOF

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('payments', '0001_initial'),
    ]

    operations = [
        # Remove unique constraint on custom_name (depends on the field)
        migrations.RemoveConstraint(
            model_name='userpaymentmethod',
            name='unique_user_custom_name',
        ),
        # Remove the custom_name field
        migrations.RemoveField(
            model_name='userpaymentmethod',
            name='custom_name',
        ),
        # Make global_method non-nullable (no existing rows, safe)
        migrations.AlterField(
            model_name='userpaymentmethod',
            name='global_method',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='user_methods',
                to='payments.globalpaymentmethod',
            ),
        ),
        # Add unique_together (replaces the UniqueConstraint from 0001)
        migrations.AlterUniqueTogether(
            name='userpaymentmethod',
            unique_together={('user', 'global_method')},
        ),
        # Update ordering
        migrations.AlterModelOptions(
            name='userpaymentmethod',
            options={
                'ordering': ['global_method__name'],
                'verbose_name': 'User Payment Method',
                'verbose_name_plural': 'User Payment Methods',
            },
        ),
    ]
