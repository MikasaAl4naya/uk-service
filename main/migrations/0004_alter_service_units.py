from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0003_alter_calculation_options_alter_service_units_and_more'),
    ]

    operations = [
        # Удаление старого поля ManyToMany
        migrations.RemoveField(
            model_name='service',
            name='units',
        ),

        # Создание новой ManyToMany через промежуточную модель
        migrations.AddField(
            model_name='service',
            name='units',
            field=models.ManyToManyField(blank=True, through='main.ServiceUnit', to='main.unit'),
        ),
    ]
