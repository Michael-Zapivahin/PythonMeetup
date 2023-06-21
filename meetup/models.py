from django.db import models


class Guest(models.Model):
    name = models.CharField(max_length=200, verbose_name='Имя')
    phone = models.CharField(max_length=12, verbose_name='Телефон', blank=True)
    friends = models.ManyToManyField('self', related_name='friends', verbose_name='Friends')
    kind_activity = models.CharField(max_length=200, verbose_name='Вид деятельности', blank=True)
    open_for_contact = models.BooleanField('Открыт для контактов', default=False)
    projects = models.TextField('Проекты', blank=True)

    def __str__(self):
        return f'{self.name}, phone: {self.phone}'


class Event(models.Model):
    topic = models.CharField(max_length=200, verbose_name='Тема')
    date = models.DateTimeField('Дата')

    def __str__(self):
        return self.topic


class Schedule(models.Model):
    topic = models.CharField(max_length=200, verbose_name='Тема')
    date_start = models.DateTimeField('Дата')
    date_end = models.DateTimeField('Дата')
    speaker = models.ForeignKey(Guest, verbose_name='Спикер', on_delete=models.PROTECT)
    active = models.BooleanField(default=False)
    event = models.ForeignKey(Event, verbose_name='Событие', on_delete=models.CASCADE)

    def __str__(self):
        return self.topic


class Question(models.Model):
    question = models.TextField('Вопрос')
    schedule = models.ForeignKey(Schedule, verbose_name='Расписание', on_delete=models.SET_NULL, null=True)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.question[100]


class Donation(models.Model):
    amount = models.IntegerField('Сумма')
    schedule = models.ForeignKey(Schedule, verbose_name='Расписание', on_delete=models.SET_NULL, null=True)
    guest = models.ForeignKey(Guest, verbose_name='Донатор', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.guest












