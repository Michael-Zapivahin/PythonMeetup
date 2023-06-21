
import datetime
from django.core.management.base import BaseCommand
import meetup.db_operations as dataset
from meetup.models import Guest, Event
import pytz


class Command(BaseCommand):
    help = ''

    def handle(self, *args, **options):
        year, month, day = options['year'], options['month'], options['day']
        day = datetime.datetime(year, month, day, 0, 0, 0, tzinfo=pytz.UTC)
        # salon = Salon.objects.filter(phone=options['salon_phone']).first()
        # master = Employee.objects.filter(phone=options['master_phone']).first()
        # print(salon, master, day)
        dataset.set_salon_schedule(day, salon=salon, employee=master)
