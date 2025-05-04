from django.urls import path
from . import views

urlpatterns = [
    path('get_units_for_service/<int:service_id>/', views.get_units_for_service, name='get_units_for_service'),
    path('', views.BuildingListView.as_view(), name='building_list'),
    path('accounts/<int:pk>/', views.AccountDetailView.as_view(), name='account_detail'),
    path('accounts/<int:account_id>/add_reading/', views.MeterReadingCreateView.as_view(), name='add_reading'),
    path('accounts/<int:account_id>/calculate/', views.CalculationCreateView.as_view(), name='calculate'),
    path('reports/charges/', views.charges_report, name='charges_report'),
    path('account/<int:account_id>/add_services/', views.add_service_to_account, name='add_service_to_account'),
    path('reports/debt/', views.debt_report, name='debt_report'),
    path('meter_reading_report/', views.meter_reading_report, name='meter_reading_report'),
    path('payment_report/', views.payment_report, name='payment_report'),
    path('add_building/', views.add_building, name='add_building'),
    path('add_room/<int:building_id>/', views.add_room, name='add_room'),
    path('add_account/', views.add_account, name='add_account'),  # Измените здесь
    path('delete_building/<int:pk>/', views.delete_building, name='delete_building'),
    path('delete_room/<int:pk>/', views.delete_room, name='delete_room'),
    path('delete_account/<int:pk>/', views.delete_account, name='delete_account'),
    path('room/edit/<int:pk>/', views.RoomUpdateView.as_view(), name='room_edit'),
    path('add_service/', views.add_service, name='add_service'),
    # Добавление тарифа для услуги
    path('add_tariff/<int:service_id>/', views.add_tariff, name='add_tariff'),
    path('service_list/', views.service_list, name='service_list'),
    path('unit_list/', views.unit_list, name='unit_list'),
    path('add_unit/', views.add_unit, name='add_unit'),
    path('tariff_list/', views.tariff_list, name='tariff_list'),
    path('service/<int:pk>/', views.service_detail, name='service_detail'),
    # Маршруты для редактирования
    path('edit_service/<int:pk>/', views.edit_service, name='edit_service'),  # Редактирование услуги
    path('edit_unit/<int:pk>/', views.edit_unit, name='edit_unit'),  # Редактирование единицы измерения
    path('edit_tariff/<int:pk>/', views.edit_tariff, name='edit_tariff'),  # Редактирование тарифа
    # Маршруты для удаления
    path('delete_service/<int:pk>/', views.delete_service, name='delete_service'),  # Удаление услуги
    path('delete_unit/<int:pk>/', views.delete_unit, name='delete_unit'),  # Удаление единицы измерения
    path('delete_tariff/<int:pk>/', views.delete_tariff, name='delete_tariff'),  # Удаление тарифа
    path('payment_list/', views.payment_list, name='payment_list'),  # Список платежей
    path('add_payment/<int:account_id>/', views.add_payment, name='add_payment'),  # Добавление платежа
    path('edit_payment/<int:pk>/', views.edit_payment, name='edit_payment'),  # Редактирование платежа
    path('delete_payment/<int:pk>/', views.delete_payment, name='delete_payment'),  # Удаление платежа
    path('account_list/', views.account_list, name='account_list'),
    path('building_debt_report/', views.building_debt_report, name='building_debt_report')

]