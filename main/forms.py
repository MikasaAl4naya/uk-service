from django import forms
from .models import *
from django.core.exceptions import ValidationError
from datetime import date
class MeterReadingForm(forms.ModelForm):
    class Meta:
        model = MeterReading
        fields = ['service', 'unit', 'value', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, account, service_queryset=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account

        # Ограничиваем доступные сервисы
        self.fields['service'].queryset = service_queryset or Service.objects.none()

        # Для фиксированных и переменных услуг
        if 'service' in self.data:
            try:
                service_id = int(self.data.get('service'))
                service = Service.objects.get(id=service_id)

                # Для фиксированных услуг скрываем поле единицы измерения
                if service.type == 'fixed':
                    self.fields['unit'].required = False
                    self.fields['unit'].widget = forms.HiddenInput()  # Скрываем поле для фиксированных услуг
                else:
                    # Для переменных услуг фильтруем единицы измерения через промежуточную модель ServiceUnit
                    self.fields['unit'].queryset = Unit.objects.filter(serviceunit__service=service)

            except (ValueError, TypeError, Service.DoesNotExist):
                pass  # Если ошибка, оставляем пустое поле

        elif self.instance.pk and self.instance.service:
            service = self.instance.service
            if service.type == 'fixed':
                self.fields['unit'].required = False
                self.fields['unit'].widget = forms.HiddenInput()  # Скрываем поле для фиксированных услуг
            else:
                self.fields['unit'].queryset = service.units.all()




class AccountServicesForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['services']  # Только поле для выбора услуг

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Вы можете ограничить выбор доступных услуг определенным фильтром, если нужно
        self.fields['services'].queryset = Service.objects.all()  # Пример, чтобы выбрать все услуги
class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'code']


class CalculationForm(forms.ModelForm):
    period = forms.CharField(
        label='Период (ГГГГ-ММ)',
        widget=forms.TextInput(attrs={'type': 'month'}))

    class Meta:
        model = Calculation
        fields = ['period']

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)

        # Установка минимальной и максимальной даты
        today = date.today()
        self.fields['period'].widget.attrs['min'] = '2000-01'
        self.fields['period'].widget.attrs['max'] = today.strftime('%Y-%m')

    def clean_period(self):
        period_str = self.cleaned_data.get('period')

        try:
            year, month = map(int, period_str.split('-'))
            period_date = date(year, month, 1)
        except (ValueError, AttributeError):
            raise ValidationError("Введите корректный период в формате ГГГГ-ММ")

        # Проверка уникальности расчета
        if Calculation.objects.filter(
                account=self.account,
                period__year=year,
                period__month=month
        ).exists():
            raise ValidationError("Расчет за этот период уже существует")

        return period_date

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = ['address']

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['building', 'number']

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'type', 'units']


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['room', 'balance']  # Указываем поля, которые можно будет редактировать

    def __init__(self, *args, **kwargs):
        room = kwargs.pop('room', None)  # Получаем значение room из kwargs
        super().__init__(*args, **kwargs)

        if room:
            self.fields['room'].initial = room  # Устанавливаем предварительное значение для поля room
class TariffForm(forms.ModelForm):
    class Meta:
        model = Tariff
        fields = ['service', 'unit', 'rate', 'start_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'})  # Используем DateInput для выбора даты
        }