# Generated by Django 5.1.3 on 2024-11-14 12:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0049_grouptag_senseboxtable_grouptags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='grouptag',
            name='tag',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
