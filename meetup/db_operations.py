import os
import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'pythonmeetup.settings'
django.setup()

from .models import Event, Schedule
from typing import NamedTuple

class Speech(NamedTuple):
    time: str
    topic: str


template_schedule = [
    Speech('10:00-11:00', ''),
    Speech('11:00-12:00', ''),
    Speech('12:00-13:00', ''),
    Speech('13:00-14:00', 'Перерыв'),
    Speech('14:00-15:00', ''),
    Speech('15:00-16:00', ''),
    Speech('16:00-17:00', ''),    
]

def get_all_events() -> list[Event]:
    return Event.objects.all()


def get_event(id) -> Event:
    return Event.objects.get(id=id)


def delete_event(id) -> None:
    Event.objects.get(id=id).delete()


def create_new_event(topic, date) -> None:
    event = Event.objects.create(topic=topic, date=date)
    Schedule.objects.bulk_create(
        [
            Schedule(
                event=event,
                start_at=speech.time.split('-')[0],
                end_at=speech.time.split('-')[1],
                topic=speech.topic
            ) 
            for speech in template_schedule
        ] 
    )

        
def get_event_schedules(event_id) -> list[Schedule]:     
    return Schedule.objects.filter(event_id=event_id).order_by('start_at')


def get_speech(speech_id) -> Schedule:
    return Schedule.objects.get(id=speech_id)


def create_speech(event_id, start_at='09:00:00', end_at='09:00:00', topic='Новое...') -> Schedule:
    return Schedule.objects.create(
        event_id=event_id,
        start_at=start_at,
        end_at=end_at,
        topic=topic
    )
    
def delete_speech(speech_id) -> None:
    Schedule.objects.get(id=speech_id).delete()


def create_guest(name, phone, email, kind, projects, public, telegram_id):
    print(name, phone, email, kind, projects, public, telegram_id)
    return None

