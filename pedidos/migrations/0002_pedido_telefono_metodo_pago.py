from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="metodo_pago",
            field=models.CharField(
                choices=[
                    ("efectivo", "Efectivo contra entrega"),
                    ("pos", "Tarjeta con POS contra entrega"),
                ],
                default="efectivo",
                max_length=20,
                verbose_name="Método de pago",
            ),
        ),
        migrations.AddField(
            model_name="pedido",
            name="telefono",
            field=models.CharField(
                blank=True,
                default="",
                max_length=15,
                verbose_name="Teléfono de contacto",
            ),
        ),
    ]
