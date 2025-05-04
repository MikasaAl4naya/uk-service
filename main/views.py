
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.db.models import Sum
from .models import *
from django.http import JsonResponse
from .forms import *
from django.db.models import Sum, F, Q
from django.utils.timezone import now
from datetime import timedelta
from django.db.models.functions import Coalesce
from django.views.generic import CreateView, UpdateView
from django.http import HttpResponse
from django.db.models import DecimalField, Value
class BuildingListView(ListView):
    model = Building
    template_name = 'building_list.html'
    context_object_name = 'buildings'


class AccountDetailView(DetailView):
    model = Account
    template_name = 'account_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['readings'] = self.object.readings.all().order_by('-date')
        context['calculations'] = self.object.calculations.all().order_by('-period')
        context['payments'] = self.object.payments.all().order_by('-date')
        return context
def add_service_to_account(request, account_id):
    account = get_object_or_404(Account, pk=account_id)

    if request.method == 'POST':
        form = AccountServicesForm(request.POST, instance=account)
        if form.is_valid():
            form.save()  # Сохраняем изменения
            return redirect('account_detail', pk=account.id)  # Перенаправляем на страницу деталей лицевого счета
    else:
        form = AccountServicesForm(instance=account)  # Предзаполнение формы для существующего лицевого счета

    return render(request, 'add_services_to_account.html', {'form': form, 'account': account})
def get_units_for_service(request, service_id):
    # Получаем единицы измерения, связанные с услугой через модель ServiceUnit
    units = Unit.objects.filter(serviceunit__service_id=service_id).values('id', 'name')
    return JsonResponse({'units': list(units)})
class MeterReadingCreateView(CreateView):
    model = MeterReading
    form_class = MeterReadingForm
    template_name = 'meter_reading_form.html'
    success_url = reverse_lazy('meter_reading_report')  # Указываем URL для перенаправления

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        account = get_object_or_404(Account, pk=self.kwargs['account_id'])
        kwargs['account'] = account
        # Ограничиваем выбор услуг только теми, которые связаны с данным лицевым счетом
        kwargs['service_queryset'] = account.services.all()  # Передаем в форму доступные услуги
        return kwargs

    def form_valid(self, form):
        form.instance.account = get_object_or_404(Account, pk=self.kwargs['account_id'])
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = get_object_or_404(Account, pk=self.kwargs['account_id'])
        context['account'] = account  # Передаем объект account в контекст
        return context


class CalculationCreateView(CreateView):
    model = Calculation
    form_class = CalculationForm
    template_name = 'calculation_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['account'] = get_object_or_404(Account, pk=self.kwargs['account_id'])
        return kwargs

    def form_valid(self, form):
        account = get_object_or_404(Account, pk=self.kwargs['account_id'])
        period = form.cleaned_data['period']

        # Проверка наличия услуг
        if not account.services.exists():
            form.add_error(None, 'К лицевому счету не привязано ни одной услуги')
            return self.form_invalid(form)

        # Проверка уникальности расчета
        if Calculation.objects.filter(account=account, period__year=period.year, period__month=period.month).exists():
            form.add_error(None, 'Расчет за этот период уже существует')
            return self.form_invalid(form)

        total = 0
        fixed_services = account.services.filter(type='fixed')

        # Проверка тарифов для фиксированных услуг
        for service in fixed_services:
            if not service.tariffs.exists():
                form.add_error(None, f'Для услуги {service.name} не установлены тарифы')
                return self.form_invalid(form)

            tariff = service.tariffs.latest('start_date')
            total += tariff.rate

        # Расчет для переменных услуг
        variable_services = account.services.filter(type='variable')
        for service in variable_services:
            readings = account.readings.filter(
                service=service,
                date__month=period.month,
                date__year=period.year
            )

            if not readings.exists():
                form.add_error(None, f'Нет показаний для услуги {service.name} за {period:%m.%Y}')
                return self.form_invalid(form)

            for reading in readings:
                if not reading.unit:
                    form.add_error(None, f'Не указана единица измерения для показания {reading.id}')
                    return self.form_invalid(form)

                tariff = service.tariffs.filter(unit=reading.unit).first()
                if not tariff:
                    form.add_error(None, f'Нет тарифа для услуги {service.name} и единицы {reading.unit}')
                    return self.form_invalid(form)

                total += reading.value * tariff.rate

        if total == 0:
            form.add_error(None, 'Сумма начисления равна 0. Проверьте данные')
            return self.form_invalid(form)

        calculation = form.save(commit=False)
        calculation.account = account
        calculation.total_amount = total
        calculation.save()

        account.balance += total
        account.save()

        return redirect('account_detail', pk=account.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = get_object_or_404(Account, pk=self.kwargs['account_id'])
        context['account'] = account  # Передаем объект account в контекст
        return context
def account_list(request):
    # Получаем все лицевые счета
    accounts = Account.objects.all()
    return render(request, 'account_list.html', {'accounts': accounts})


def building_debt_report(request):
    current_date = now().date()
    three_months_ago = current_date - timedelta(days=90)

    buildings = Building.objects.prefetch_related('rooms__account').all()
    report_data = {}

    for building in buildings:
        # Получаем все счета, связанные с помещениями в здании
        accounts = Account.objects.filter(room__building=building)

        # Аннотируем задолженность для каждого счета
        debt_data = accounts.annotate(
            total_charges=Sum(
                'calculations__total_amount',
                filter=Q(calculations__period__gte=three_months_ago),
                output_field=DecimalField()  # Явно указываем DecimalField для total_charges
            ),
            total_payments=Sum(
                'payments__amount',
                filter=Q(payments__date__gte=three_months_ago),
                output_field=DecimalField()  # Явно указываем DecimalField для total_payments
            ),
            debt=Coalesce(
                F('total_charges'), 0, output_field=DecimalField()
            ) - Coalesce(
                F('total_payments'), 0, output_field=DecimalField()
            )
        ).filter(debt__gt=0)  # Фильтруем только те записи, где задолженность больше 0

        # Суммируем задолженность по всем счетам для каждого здания
        total_debt = debt_data.aggregate(total=Sum('debt', output_field=DecimalField()))['total'] or 0

        # Группируем задолженность по периодам для каждого счета
        period_data = {}
        for account in debt_data:
            calculations = Calculation.objects.filter(account=account)
            for calculation in calculations:
                period_key = calculation.period.strftime("%m.%Y")  # Форматируем период как ММ.ГГГГ
                if period_key not in period_data:
                    period_data[period_key] = {
                        'accounts': [],
                        'total_debt': 0
                    }
                period_data[period_key]['accounts'].append(account)
                period_data[period_key]['total_debt'] += account.debt  # Суммируем задолженность по периодам

        # Добавляем данные в отчет
        report_data[building] = {
            'total_debt': total_debt,
            'period_data': period_data
        }

    context = {
        'report_data': report_data,
        'current_date': current_date.strftime("%d.%m.%Y"),
        'period': f"{three_months_ago.strftime('%d.%m.%Y')} - {current_date.strftime('%d.%m.%Y')}"
    }

    # Отправляем данные в шаблон
    return render(request, 'reports/building_debt_report.html', context)


def charges_report(request):
    period = request.GET.get('period')
    calculations = Calculation.objects.select_related('account', 'account__room', 'account__room__building')

    if period:
        try:
            year, month = map(int, period.split('-'))
            calculations = calculations.filter(period__year=year, period__month=month)
        except ValueError:
            return HttpResponse("Некорректный формат периода. Используйте формат YYYY-MM.", status=400)

    if not calculations.exists():
        return HttpResponse("Нет данных для выбранного периода.", status=200)

    report_data = {}
    total_amount = calculations.aggregate(total=Sum('total_amount'))['total'] or 0

    for calc in calculations:
        period_key = calc.period.strftime("%m.%Y")
        if period_key not in report_data:
            report_data[period_key] = []

        report_data[period_key].append({
            'account': calc.account,
            'amount': calc.total_amount
        })

    context = {
        'report_data': report_data,
        'total_amount': total_amount,
        'period': period
    }
    return render(request, 'reports/charges_report.html', context)


def payment_report(request):
    payments = Payment.objects.select_related('account').order_by('-date')

    # Фильтрация по периоду
    period = request.GET.get('period')
    if period:
        try:
            year, month = map(int, period.split('-'))
            payments = payments.filter(date__year=year, date__month=month)
        except ValueError:
            messages.error(request, "Некорректный формат периода. Используйте ГГГГ-ММ")

    context = {
        'payments': payments,
        'total_amount': payments.aggregate(Sum('amount'))['amount__sum'] or 0,
        'period': period
    }
    return render(request, 'reports/payment_report.html', context)
def add_building(request):
    if request.method == "POST":
        form = BuildingForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('building_list')  # Перенаправление на список строений
    else:
        form = BuildingForm()
    return render(request, 'add_building.html', {'form': form})
def add_account(request):
    room_id = request.GET.get('room_id')
    room = None
    if room_id:
        room = get_object_or_404(Room, id=room_id)

    if request.method == 'POST':
        form = AccountForm(request.POST, room=room)  # Передаем room в форму
        if form.is_valid():
            account = form.save(commit=False)
            if room:
                account.room = room  # Привязываем лицевой счет к конкретному помещению
            account.save()
            return redirect('account_list')  # Перенаправляем на список лицевых счетов
    else:
        form = AccountForm(room=room)

    return render(request, 'add_account.html', {'form': form, 'room': room})
class RoomUpdateView(UpdateView):
    model = Room
    form_class = RoomForm
    template_name = 'room_form.html'
    success_url = reverse_lazy('building_list')
def delete_building(request, pk):
    building = get_object_or_404(Building, pk=pk)
    building.delete()
    return redirect('building_list')

def delete_room(request, pk):
    room = get_object_or_404(Room, pk=pk)
    room.delete()
    return redirect('building_list')

def delete_account(request, pk):
    account = get_object_or_404(Account, pk=pk)
    account.delete()
    return redirect('account_list')
def add_room(request, building_id):
    building = Building.objects.get(id=building_id)
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.building = building
            room.save()
            return redirect('building_list')  # Перенаправляем на список строений
    else:
        form = RoomForm()

    return render(request, 'add_room.html', {'form': form, 'building': building})
def debt_report(request):
    current_date = now().date()
    three_months_ago = current_date - timedelta(days=90)

    # Аннотируем задолженность по лицевым счетам
    accounts = Account.objects.annotate(
        total_charges=Sum('calculations__total_amount',
                          filter=Q(calculations__period__gte=three_months_ago),
                          output_field=DecimalField()),
        total_payments=Sum('payments__amount',
                           filter=Q(payments__date__gte=three_months_ago),
                           output_field=DecimalField())
    ).annotate(
        debt=Coalesce(F('total_charges'), 0) - Coalesce(F('total_payments'), 0)
    ).filter(debt__gt=0)  # Фильтруем только те счета, у которых есть задолженность

    # Группировка данных по периодам
    period_data = {}
    for acc in accounts:
        period = three_months_ago.strftime("%m.%Y") + " - " + current_date.strftime("%m.%Y")
        if period not in period_data:
            period_data[period] = {
                'accounts': [],
                'total_debt': 0
            }
        period_data[period]['accounts'].append(acc)
        period_data[period]['total_debt'] += acc.debt

    context = {
        'period_data': period_data,
        'current_date': current_date
    }
    return render(request, 'reports/debt_report.html', context)



def meter_reading_report(request):
    period = request.GET.get('period')
    readings = MeterReading.objects.all()

    if period:
        try:
            year, month = map(int, period.split('-'))
            readings = readings.filter(date__year=year, date__month=month)
        except ValueError:
            return HttpResponse("Некорректный формат периода. Используйте формат YYYY-MM.", status=400)

    # Группировка по услуге и месяцам
    report_data = {}
    for reading in readings:
        service_key = reading.service.name
        if service_key not in report_data:
            report_data[service_key] = {}

        period_key = reading.date.strftime("%m.%Y")
        if period_key not in report_data[service_key]:
            report_data[service_key][period_key] = []

        report_data[service_key][period_key].append(reading)

    context = {
        'report_data': report_data,
    }
    return render(request, 'reports/meter_reading_report.html', context)


    # Группировка по услуге и месяцам
    report_data = {}
    for reading in readings:
        service_key = reading.service.name
        if service_key not in report_data:
            report_data[service_key] = {}

        period_key = reading.date.strftime("%m.%Y")
        if period_key not in report_data[service_key]:
            report_data[service_key][period_key] = []

        report_data[service_key][period_key].append(reading)

    context = {
        'report_data': report_data,
    }
    return render(request, 'reports/meter_reading_report.html', context)


def add_service(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('service_list')  # Перенаправляем на страницу списка услуг
    else:
        form = ServiceForm()
    return render(request, 'add_service.html', {'form': form})

def service_list(request):
    services = Service.objects.all()  # Получаем все услуги
    return render(request, 'service_list.html', {'services': services})
def add_tariff(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        form = TariffForm(request.POST)
        if form.is_valid():
            tariff = form.save(commit=False)
            tariff.service = service  # Привязываем тариф к услуге
            tariff.save()
            return redirect('service_detail', pk=service.id)  # Перенаправляем на страницу услуги
    else:
        form = TariffForm()
    return render(request, 'add_tariff.html', {'form': form, 'service': service})
def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk)  # Получаем услугу по её ID
    # Передаем услугу в шаблон, а также её тарифы и единицы измерения
    return render(request, 'service_detail.html', {'service': service})
# views.py
def unit_list(request):
    units = Unit.objects.all()
    return render(request, 'unit_list.html', {'units': units})

def tariff_list(request):
    services = Service.objects.all()  # Получаем все услуги
    return render(request, 'tariff_list.html', {'services': services})

# views.py
def add_unit(request):
    if request.method == 'POST':
        form = UnitForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('unit_list')  # Перенаправляем на список единиц измерения
    else:
        form = UnitForm()

    return render(request, 'add_unit.html', {'form': form})

def delete_tariff(request, pk):
    tariff = get_object_or_404(Tariff, pk=pk)
    tariff.delete()
    return redirect('tariff_list')  # Перенаправляем на список тарифов

def edit_tariff(request, pk):
    tariff = get_object_or_404(Tariff, pk=pk)
    if request.method == 'POST':
        form = TariffForm(request.POST, instance=tariff)
        if form.is_valid():
            form.save()
            return redirect('tariff_list')  # Перенаправляем на список тарифов
    else:
        form = TariffForm(instance=tariff)
    return render(request, 'edit_tariff.html', {'form': form})

def delete_unit(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    unit.delete()
    return redirect('unit_list')  # Перенаправляем на список единиц измерения

def edit_unit(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    if request.method == 'POST':
        form = UnitForm(request.POST, instance=unit)
        if form.is_valid():
            form.save()
            return redirect('unit_list')  # Перенаправляем на список единиц измерения
    else:
        form = UnitForm(instance=unit)
    return render(request, 'edit_unit.html', {'form': form})

def delete_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service.delete()
    return redirect('service_list')  # Перенаправляем на список услуг
def edit_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('service_list')  # Перенаправляем на список услуг
    else:
        form = ServiceForm(instance=service)
    return render(request, 'edit_service.html', {'form': form})
def payment_list(request):
    payments = Payment.objects.all()  # Получаем все платежи
    return render(request, 'payment_list.html', {'payments': payments})

def add_payment(request, account_id):
    account = get_object_or_404(Account, id=account_id)
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.account = account  # Привязываем платеж к лицевому счету
            payment.save()
            return redirect('payment_list')  # Перенаправляем на список платежей
    else:
        form = PaymentForm()

    return render(request, 'add_payment.html', {'form': form, 'account': account})

def edit_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            return redirect('payment_list')  # Перенаправляем на список платежей
    else:
        form = PaymentForm(instance=payment)
    return render(request, 'edit_payment.html', {'form': form})

def delete_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    payment.delete()
    return redirect('payment_list')  # Перенаправляем на список платежей