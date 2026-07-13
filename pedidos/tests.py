from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from catalogo.models import Negocio, Producto, Categoria
from pedidos.models import Pedido, ItemPedido

User = get_user_model()

class CuponNATIVO50TestCase(TestCase):
    def setUp(self):
        # 1. Crear usuario cliente
        self.cliente = User.objects.create_user(
            username="cliente_test",
            email="cliente@test.com",
            password="password123",
            rol="cliente",
            telefono="999888777",
            direccion="Direccion Test",
            latitud=Decimal("-12.046374"),
            longitud=Decimal("-77.042793")
        )
        
        # 2. Crear usuario negocio
        self.vendedor = User.objects.create_user(
            username="vendedor_test",
            email="vendedor@test.com",
            password="password123",
            rol="negocio"
        )
        
        # 3. Crear negocio
        self.negocio = Negocio.objects.create(
            propietario=self.vendedor,
            nombre_comercial="Tienda Test",
            rubro="restaurante",
            direccion="Calle Falsa 123",
            latitud=Decimal("-12.046374"),
            longitud=Decimal("-77.042793"),
            costo_envio=Decimal("10.00"),
            abierto=True
        )
        
        # 4. Crear categoria
        self.categoria = Categoria.objects.create(
            nombre="Comida"
        )
        
        # 5. Crear producto
        self.producto = Producto.objects.create(
            negocio=self.negocio,
            categoria=self.categoria,
            nombre="Hamburguesa",
            precio=Decimal("40.00"),
            stock=10,
            disponible=True
        )

    def test_aplicar_cupon_primer_pedido(self):
        self.client.login(username="cliente_test", password="password123")
        
        # Agregar al carrito
        response_add = self.client.post(reverse("pedidos:agregar_al_carrito", args=[self.producto.id]), {"cantidad": 2})
        self.assertEqual(response_add.status_code, 302)
        
        # Aplicar cupón NATIVO50
        response_coupon = self.client.post(reverse("pedidos:aplicar_cupon"), {"codigo_cupon": "NATIVO50"})
        self.assertEqual(response_coupon.status_code, 302)
        self.assertEqual(self.client.session.get("cupon_aplicado"), "NATIVO50")
        
        # Procesar carrito
        response_checkout = self.client.post(reverse("pedidos:procesar_carrito"), {
            "direccion_entrega": "Direccion Test",
            "telefono": "999888777",
            "metodo_pago": "efectivo",
            "observaciones": ""
        })
        self.assertEqual(response_checkout.status_code, 302)
        
        # Verificar pedido creado
        pedido = Pedido.objects.filter(cliente=self.cliente).first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.cupon, "NATIVO50")
        # Subtotal: 2 * 40.00 = 80.00
        self.assertEqual(pedido.subtotal, Decimal("80.00"))
        # Descuento: 25% de 80.00 = 20.00
        self.assertEqual(pedido.descuento, Decimal("20.00"))
        # Costo Envio: 10.00
        self.assertEqual(pedido.costo_envio, Decimal("10.00"))
        # Total: 80.00 - 20.00 + 10.00 = 70.00
        self.assertEqual(pedido.total, Decimal("70.00"))

    def test_rehusar_cupon_segundo_pedido(self):
        self.client.login(username="cliente_test", password="password123")
        
        # Crear un primer pedido directamente en BD
        Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            direccion_entrega="Direccion Test",
            telefono="999888777",
            metodo_pago="efectivo",
            subtotal=Decimal("40.00"),
            costo_envio=Decimal("10.00"),
            total=Decimal("50.00"),
            estado="EN" # Entregado
        )
        
        # Agregar al carrito para el segundo pedido
        self.client.post(reverse("pedidos:agregar_al_carrito", args=[self.producto.id]), {"cantidad": 2})
        
        # Intentar aplicar cupón NATIVO50
        response_coupon = self.client.post(reverse("pedidos:aplicar_cupon"), {"codigo_cupon": "NATIVO50"})
        self.assertEqual(response_coupon.status_code, 302)
        # Debe rehusarse porque ya tiene compras previas
        self.assertIsNone(self.client.session.get("cupon_aplicado"))

from django.contrib.messages import get_messages

class StockAlertAndVisibilityTestCase(TestCase):
    def setUp(self):
        # Create users
        self.cliente = User.objects.create_user(
            username="cliente_test2",
            email="cliente2@test.com",
            password="password123",
            rol="cliente"
        )
        self.vendedor = User.objects.create_user(
            username="vendedor_test2",
            email="vendedor2@test.com",
            password="password123",
            rol="negocio"
        )
        # Create business
        self.negocio = Negocio.objects.create(
            propietario=self.vendedor,
            nombre_comercial="Tienda Test 2",
            rubro="restaurante",
            direccion="Calle Falsa 123",
            abierto=True
        )
        self.categoria = Categoria.objects.create(nombre="Comida")
        # Create product with low stock (2)
        self.producto = Producto.objects.create(
            negocio=self.negocio,
            categoria=self.categoria,
            nombre="Hamburguesa Low Stock",
            precio=Decimal("15.00"),
            stock=2,
            disponible=True
        )

    def test_low_stock_alert_on_business_panel(self):
        # Login as business owner
        self.client.login(username="vendedor_test2", password="password123")
        
        # Access business panel
        response = self.client.get(reverse("pedidos:panel_negocio"))
        self.assertEqual(response.status_code, 200)
        
        # Check low stock products context
        bajo_stock = list(response.context["productos_bajo_stock"])
        self.assertIn(self.producto, bajo_stock)
        
        # Check warning messages
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("¡Alerta de inventario bajo!" in str(m) for m in messages))

    def test_zero_stock_product_visibility(self):
        # Set product stock to 0
        self.producto.stock = 0
        self.producto.save()

        # Login as client
        self.client.login(username="cliente_test2", password="password123")
        
        # View business detail page
        response = self.client.get(reverse("detalle_negocio", args=[self.negocio.id]))
        self.assertEqual(response.status_code, 200)
        
        # Client should see 0 products (since Hamburguesa is out of stock)
        productos_cliente = list(response.context["productos"])
        self.assertNotIn(self.producto, productos_cliente)

        # Login as business owner
        self.client.login(username="vendedor_test2", password="password123")
        
        # View business administration page
        response_admin = self.client.get(reverse("administrar_productos"))
        self.assertEqual(response_admin.status_code, 200)
        
        # Business owner should still see the product in CRUD
        productos_admin = list(response_admin.context["productos"])
        self.assertIn(self.producto, productos_admin)
