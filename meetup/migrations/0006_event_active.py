# Generated by Django 4.2.2 on 2023-06-23 05:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meetup', '0005_alter_schedule_topic'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='active',
            field=models.BooleanField(default=False),
        ),
    ]