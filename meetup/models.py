from django.db import models


class Guest(models.Model):
    name = models.CharField(max_length=200, verbose_name='Имя')
    phone = models.CharField(max_length=12, verbose_name='Телефон', blank=True, null=True)
    friends = models.ManyToManyField('self', through='friend')
    kind_activity = models.CharField(max_length=200, verbose_name='Вид деятельности', blank=True)
    open_for_contact = models.BooleanField('Открыт для контактов', default=False)
    projects = models.TextField('Проекты', blank=True)
    telegram_id = models.IntegerField('Телеграм ID', unique=True)

    class Meta:
        verbose_name = 'посетитель'
        verbose_name_plural = 'посетители'
        
    def __str__(self):
        return f'{self.name}, phone: {self.phone}'


class Friend(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='me')
    friend = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='friend')

    class Meta:
        verbose_name = 'друг'
        verbose_name_plural = 'друзья'

    def __str__(self):
        return f'{self.friend}'


class Event(models.Model):
    topic = models.CharField(max_length=200, verbose_name='Тема')
    date = models.DateField('Дата')
    guests = models.ManyToManyField(Guest, through='EventGuests')
    active = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'мероприятие'
        verbose_name_plural = 'мероприятия'

    def __str__(self):
        return self.topic


class EventGuests(models.Model):
    event = models.ForeignKey(Event, related_name='events', on_delete=models.CASCADE)
    guest = models.ForeignKey(Guest, related_name='events', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'гость мероприятия'
        verbose_name_plural = 'гости мероприятия'


class Schedule(models.Model):
    topic = models.CharField(max_length=200, verbose_name='Тема', blank=True)
    start_at = models.TimeField('Время начала выступления', null=True)
    end_at = models.TimeField('Время окончания выступления', null=True, blank=True)
    speaker = models.ForeignKey(
        Guest,
        verbose_name='Спикер',
        on_delete=models.PROTECT,
        related_name='schedules',
        null=True,
        blank=True
    )
    active = models.BooleanField(default=False)
    event = models.ForeignKey(Event, verbose_name='Событие', on_delete=models.CASCADE, related_name='schedules')

    class Meta:
        verbose_name = 'доклад'
        verbose_name_plural = 'доклады'

    def __str__(self):
        return self.topic


class Question(models.Model):
    question = models.TextField('Вопрос')
    schedule = models.ForeignKey(Schedule, verbose_name='Расписание', on_delete=models.SET_NULL, null=True, related_name='questions')
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, null=True, related_name='questions')

    class Meta:
        verbose_name = 'вопрос'
        verbose_name_plural = 'вопросы'

    def __str__(self):
        return self.question[:100]


class Donation(models.Model):
    amount = models.IntegerField('Сумма')
    guest = models.ForeignKey(Guest, verbose_name='Донатор', on_delete=models.SET_NULL, null=True, related_name='donations')
    event = models.ForeignKey(
        Event, verbose_name='Событие',
        on_delete=models.SET_NULL,
        null=True,
        related_name='donations'
    )

    class Meta:
        verbose_name = 'донат'
        verbose_name_plural = 'донаты'

    def __str__(self):
        return f'{self.guest}: {self.amount}'












