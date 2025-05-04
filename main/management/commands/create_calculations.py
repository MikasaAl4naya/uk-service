from django.core.management.base import BaseCommand
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from main.models import Account, Calculation
from main.forms import CalculationForm
from django.db.models import F, Q

class Command(BaseCommand):
    help = 'Создает начисления для всех лицевых счетов за текущий месяц'

    def handle(self, *args, **kwargs):
        current_date = now().date()
        period = current_date.replace(day=1)  # Первый день текущего месяца

        # Получаем все лицевые счета
        accounts = Account.objects.all()

        for account in accounts:
            # Проверка на уникальность расчета для данного лицевого счета и месяца
            if Calculation.objects.filter(account=account, period__year=period.year, period__month=period.month).exists():
                self.stdout.write(self.style.ERROR(f"Для лицевого счета {account} уже существует расчет за период {period:%m.%Y}"))
                continue

            total = 0
            # Расчет для фиксированных услуг
            fixed_services = account.services.filter(type='fixed')
            for service in fixed_services:
                tariff = service.tariffs.latest('start_date')
                total += tariff.rate

            # Расчет для переменных услуг
            readings = account.readings.filter(date__month=period.month, date__year=period.year)
            for reading in readings:
                tariff = reading.service.tariffs.filter(unit=reading.unit).latest('start_date')
                total += reading.value * tariff.rate

            # Создаем начисление
            calculation = Calculation(
                account=account,
                period=period,
                total_amount=total
            )
            calculation.save()

            # Обновляем баланс
            account.balance += total
            account.save()

            self.stdout.write(self.style.SUCCESS(f'Начисление успешно создано для лицевого счета {account} за период {period:%m.%Y}'))
