# Generated manually — migration 0010 only added is_global to Django state,
# not to the actual database. This migration creates the column for real.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('coins', '0010_alter_orderpayment_payment_method_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE coins_orderpayment ADD COLUMN IF NOT EXISTS is_global BOOLEAN DEFAULT TRUE;",
            reverse_sql="ALTER TABLE coins_orderpayment DROP COLUMN IF EXISTS is_global;",
        ),
    ]
