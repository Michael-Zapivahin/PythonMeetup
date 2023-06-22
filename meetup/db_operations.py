import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'pythonmeetup.settings'
django.setup()

from .models import Event


def get_all_events() -> list[Event]:
    return Event.objects.all()


def get_event_by_id(id) -> Event:
    return Event.objects.get(id=id)


def create_new_event(topic, date) -> None:
    Event.objects.create(topic=topic, date=date)


def create_guest(name, phone, email, kind, projects, public, telegram_id):
    print(name, phone, email, kind, projects, public, telegram_id)
    return None
