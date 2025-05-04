from django.db import models
from django.core.exceptions import ValidationError


class Building(models.Model):
    address = models.CharField("Адрес", max_length=200, unique=True)

    def __str__(self):
        return self.address


class Room(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='rooms')
    number = models.CharField("Номер помещения", max_length=10)

    class Meta:
        unique_together = ('building', 'number')

    def __str__(self):
        return f"{self.building}, кв. {self.number}"


class Unit(models.Model):
    name = models.CharField("Единица измерения", max_length=20)
    code = models.CharField("Код", max_length=10, unique=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Service(models.Model):
    SERVICE_TYPES = (
        ('fixed', 'Постоянный'),
        ('variable', 'Переменный'),
    )
    name = models.CharField("Название", max_length=100, unique=True)
    type = models.CharField("Тип", max_length=10, choices=SERVICE_TYPES)
    units = models.ManyToManyField(Unit, blank=True, through='ServiceUnit')

    def __str__(self):
        return self.name


class Tariff(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='tariffs')
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, null=True, blank=True,)
    rate = models.DecimalField("Тариф", max_digits=10, decimal_places=2)
    start_date = models.DateField("Дата начала действия")

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.service} - {self.rate}/{self.unit.code}"


class Account(models.Model):
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='account')
    services = models.ManyToManyField(Service)
    balance = models.DecimalField("Баланс", max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"Лицевой счет {self.room}"


class MeterReading(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='readings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    value = models.DecimalField("Значение", max_digits=10, decimal_places=2)
    date = models.DateField("Дата показания")

    class Meta:
        unique_together = ('account', 'service', 'date')
        ordering = ['-date']

    def clean(self):
        if self.service.type != 'variable':
            raise ValidationError("Показания можно вводить только для услуг переменного типа")

class ServiceUnit(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    is_default = models.BooleanField(default=False)
class Calculation(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='calculations')
    period = models.DateField("Период расчета")  # Храним первый день месяца расчета
    total_amount = models.DecimalField("Сумма начисления", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        unique_together = ('account', 'period')
        ordering = ['-period']
        get_latest_by = 'period'  # Указываем поле для получения последнего объекта
    def __str__(self):
        return f"Начисление {self.account} за {self.period:%m.%Y}"


class Payment(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    date = models.DateField("Дата оплаты")

    class Meta:
        ordering = ['-date']

    def save(self, *args, **kwargs):
        self.account.balance -= self.amount
        self.account.save()
        super().save(*args, **kwargs)