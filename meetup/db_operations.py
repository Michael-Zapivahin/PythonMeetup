import os
import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'pythonmeetup.settings'
django.setup()

from .models import Event, Schedule, Guest, Question, EventGuests
from typing import NamedTuple

from django.shortcuts import get_object_or_404
from django.http import Http404

from datetime import datetime

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


def update_event(event_id, topic, date) -> None:
    Event.objects.filter(id=event_id).update(topic=topic, date=date)    


def get_event_schedules(event_id) -> list[Schedule]:
    return Schedule.objects.filter(event_id=event_id).order_by('start_at')


def get_active_event_schedule(event_id) -> Schedule:
    active_schedule = Schedule.objects.filter(event_id=event_id, active=True).first()
    
    return active_schedule if active_schedule else None


def set_active_schedule(speech_id) -> None:
      Schedule.objects.all().update(active=False)
      Schedule.objects.filter(id=speech_id).update(active=True)
    

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


def update_speech(speech_id: int, update_speech_data: dict) -> Speech:

    Schedule.objects.filter(id=speech_id).update(**update_speech_data)
 
    return Schedule.objects.get(id=speech_id)
 

def update_speech_speaker(speech_id: int, update_speech_data: dict) -> Speech:
    telegram_id = update_speech_data['speaker_id']
    name = update_speech_data['speaker_name']
    
    speaker, _ = Guest.objects.update_or_create(telegram_id=telegram_id, defaults={'name': name})
    Schedule.objects.filter(id=speech_id).update(speaker=speaker)
 
    return Schedule.objects.get(id=speech_id)
    

def add_guest_to_event(telegram_id, event):
    guest, _ = Guest.objects.update_or_create(telegram_id=telegram_id)
    EventGuests.objects.update_or_create(guest=guest, event=event)


def create_guest(name, phone, kind, projects, public, telegram_id) -> None:
    Guest.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={
            'name': name,
            'phone': phone,
            'kind_activity': kind,
            'projects': projects,
            'open_for_contact': public,
        }
    )

def set_active_event(event_id) -> Event:
    
    Event.objects.all().update(active=False)
    current_event = Event.objects.get(id=event_id)
    current_event.active = True
    current_event.save()
    
    return current_event


def get_active_event() -> Event:
    return Event.objects.filter(date__gte=datetime.today(), active=True).first()


def get_guest(telegram_id) -> Guest:
    try:
        return get_object_or_404(Guest, telegram_id=telegram_id)
    except Http404:
        pass


def get_active_schedule():
    try:
        return get_object_or_404(Schedule, active=True)
    except Http404:
        return


def create_question(question, schedule, guest):
    Question.objects.create(question=question, schedule=schedule, guest=guest)

