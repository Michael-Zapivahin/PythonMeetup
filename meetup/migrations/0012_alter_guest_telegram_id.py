# Generated by Django 4.2.2 on 2023-06-22 05:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meetup', '0011_guest_telegram_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guest',
            name='telegram_id',
            field=models.IntegerField(verbose_name='Телеграм ID'),
        ),
    ]