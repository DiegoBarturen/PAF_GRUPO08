from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from catalogo.models import Categoria, Negocio, Producto
from config.choices import EstadoPedido
from pedidos.models import ItemPedido, Pedido
from usuarios.models import Usuario

from .models import AsignacionPedido, HistorialEntrega, PerfilRepartidor


class LogisticaBaseTestCase(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.repartidor = Usuario.objects.create_user(
            username="repartidor1",
            password="testpass123",
            rol="repartidor",
        )
        self.otro_repartidor = Usuario.objects.create_user(
            username="repartidor2",
            password="testpass123",
            rol="repartidor",
        )
        self.cliente = Usuario.objects.create_user(
            username="cliente1",
            password="testpass123",
            rol="cliente",
        )
        self.negocio_usuario = Usuario.objects.create_user(
            username="negocio1",
            password="testpass123",
            rol="negocio",
        )
        self.categoria = Categoria.objects.create(
            nombre="Comida rapida",
            descripcion="Categoria de prueba",
        )
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_usuario,
            nombre_comercial="Hamburguesas Norte",
            descripcion="Negocio de prueba",
            direccion="Av. Principal 123",
            telefono="999888777",
            abierto=True,
        )
        self.producto = Producto.objects.create(
            negocio=self.negocio,
            categoria=self.categoria,
            nombre="Hamburguesa clasica",
            descripcion="Producto de prueba",
            precio=Decimal("18.50"),
            stock=10,
            disponible=True,
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            estado=EstadoPedido.LISTO_RECOJO,
            costo_envio=Decimal("5.00"),
            direccion_entrega="Jr. Las Flores 456",
            observaciones="Tocar el timbre",
        )
        ItemPedido.objects.create(
            pedido=self.pedido,
            producto=self.producto,
            cantidad=2,
        )
        self.pedido.refresh_from_db()
        self.perfil_repartidor = PerfilRepartidor.objects.create(
            usuario=self.repartidor,
            vehiculo="Moto lineal",
        )
        self.asignacion = AsignacionPedido.objects.create(
            pedido=self.pedido,
            repartidor=self.repartidor,
        )


class PerfilRepartidorModelTests(LogisticaBaseTestCase):
    def test_crea_perfil_repartidor_valido(self):
        self.assertEqual(self.perfil_repartidor.usuario, self.repartidor)
        self.assertEqual(
            self.perfil_repartidor.estado_actual,
            PerfilRepartidor.EstadoActual.DISPONIBLE,
        )

    def test_rechaza_perfil_para_usuario_no_repartidor(self):
        with self.assertRaises(ValidationError):
            PerfilRepartidor.objects.create(
                usuario=self.cliente,
                vehiculo="Bicicleta",
            )


class AsignacionPedidoModelTests(LogisticaBaseTestCase):
    def test_asignacion_valida_a_repartidor(self):
        self.assertTrue(self.asignacion.activa)
        self.assertEqual(self.asignacion.repartidor, self.repartidor)

    def test_rechaza_asignacion_a_usuario_no_repartidor(self):
        otro_pedido = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            estado=EstadoPedido.LISTO_RECOJO,
            costo_envio=Decimal("4.00"),
            direccion_entrega="Calle Secundaria 789",
        )
        ItemPedido.objects.create(
            pedido=otro_pedido,
            producto=self.producto,
            cantidad=1,
        )

        with self.assertRaises(ValidationError):
            AsignacionPedido.objects.create(
                pedido=otro_pedido,
                repartidor=self.cliente,
            )


class LogisticaApiTests(LogisticaBaseTestCase):
    def test_mi_perfil_api_devuelve_perfil_repartidor(self):
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.get(reverse("logistica:mi_perfil_api"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["usuario_id"], self.repartidor.id)
        self.assertEqual(data["username"], self.repartidor.username)
        self.assertEqual(data["vehiculo"], "Moto lineal")

    def test_mi_perfil_api_actualiza_vehiculo(self):
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.patch(
            reverse("logistica:mi_perfil_api"),
            {
                "vehiculo": "Moto electrica",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.perfil_repartidor.refresh_from_db()
        self.assertEqual(self.perfil_repartidor.vehiculo, "Moto electrica")

    def test_mi_perfil_api_permite_pasar_a_inactivo_sin_pedido_activo(self):
        self.asignacion.activa = False
        self.asignacion.entregado_en = self.asignacion.asignado_en
        self.asignacion.save(update_fields=["activa", "entregado_en"])
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.patch(
            reverse("logistica:mi_perfil_api"),
            {
                "estado_actual": PerfilRepartidor.EstadoActual.INACTIVO,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.perfil_repartidor.refresh_from_db()
        self.assertEqual(
            self.perfil_repartidor.estado_actual,
            PerfilRepartidor.EstadoActual.INACTIVO,
        )

    def test_mi_perfil_api_rechaza_pasar_a_inactivo_con_pedido_activo(self):
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.patch(
            reverse("logistica:mi_perfil_api"),
            {
                "estado_actual": PerfilRepartidor.EstadoActual.INACTIVO,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pedido activo", response.json()["detail"].lower())

    def test_mi_perfil_api_rechaza_estado_en_ruta_manual(self):
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.patch(
            reverse("logistica:mi_perfil_api"),
            {
                "estado_actual": PerfilRepartidor.EstadoActual.EN_RUTA,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("estado_actual", data)
        self.assertTrue(any("válida" in mensaje or "valida" in mensaje for mensaje in data["estado_actual"]))

    def test_mi_pedido_activo_api_devuelve_asignacion_actual(self):
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.get(reverse("logistica:mi_pedido_activo_api"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pedido_id"], self.pedido.id)
        self.assertEqual(data["estado"], EstadoPedido.LISTO_RECOJO)
        self.assertEqual(data["cliente"], self.cliente.username)
        self.assertEqual(data["negocio"], self.negocio.nombre_comercial)

    def test_mi_historial_api_devuelve_entregas_del_repartidor(self):
        HistorialEntrega.objects.create(
            pedido=self.pedido,
            repartidor=self.repartidor,
            evento=HistorialEntrega.EventoEntrega.ASIGNADO,
            observacion="Pedido asignado al repartidor.",
        )
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.get(reverse("logistica:mi_historial_api"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["pedido_id"], self.pedido.id)
        self.assertEqual(data[0]["evento"], HistorialEntrega.EventoEntrega.ASIGNADO)

    def test_mi_resumen_api_devuelve_metricas_operativas(self):
        HistorialEntrega.objects.create(
            pedido=self.pedido,
            repartidor=self.repartidor,
            evento=HistorialEntrega.EventoEntrega.ENTREGADO,
            observacion="Entrega completada.",
        )
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.get(reverse("logistica:mi_resumen_api"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["repartidor"], self.repartidor.username)
        self.assertEqual(data["pedido_activo_id"], self.pedido.id)
        self.assertEqual(data["total_asignaciones"], 1)
        self.assertEqual(data["total_entregas_completadas"], 1)

    def test_endpoint_ubicacion_actualiza_coordenadas(self):
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.post(
            reverse("logistica:actualizar_ubicacion_repartidor", args=[self.repartidor.id]),
            {"latitud": "-6.771234", "longitud": "-79.840321"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.perfil_repartidor.refresh_from_db()
        self.assertEqual(str(self.perfil_repartidor.latitud), "-6.771234")
        self.assertEqual(str(self.perfil_repartidor.longitud), "-79.840321")

    def test_confirmar_recojo_cambia_estado_a_en_camino(self):
        self.client_api.force_authenticate(user=self.repartidor)

        response = self.client_api.post(
            reverse("logistica:confirmar_recojo", args=[self.pedido.id]),
            {"observacion": "Pedido recogido en tienda."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pedido.refresh_from_db()
        self.asignacion.refresh_from_db()
        self.perfil_repartidor.refresh_from_db()

        self.assertEqual(self.pedido.estado, EstadoPedido.EN_CAMINO)
        self.assertEqual(self.pedido.repartidor, self.repartidor)
        self.assertIsNotNone(self.asignacion.recogido_en)
        self.assertEqual(
            self.perfil_repartidor.estado_actual,
            PerfilRepartidor.EstadoActual.EN_RUTA,
        )
        self.assertTrue(
            HistorialEntrega.objects.filter(
                pedido=self.pedido,
                repartidor=self.repartidor,
                evento=HistorialEntrega.EventoEntrega.RECOGIDO,
            ).exists()
        )

    def test_confirmar_entrega_cambia_estado_a_entregado(self):
        self.client_api.force_authenticate(user=self.repartidor)

        self.client_api.post(
            reverse("logistica:confirmar_recojo", args=[self.pedido.id]),
            {"observacion": "Pedido recogido."},
            format="json",
        )
        response = self.client_api.post(
            reverse("logistica:confirmar_entrega", args=[self.pedido.id]),
            {"observacion": "Pedido entregado al cliente."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pedido.refresh_from_db()
        self.asignacion.refresh_from_db()
        self.perfil_repartidor.refresh_from_db()

        self.assertEqual(self.pedido.estado, EstadoPedido.ENTREGADO)
        self.assertFalse(self.asignacion.activa)
        self.assertIsNotNone(self.asignacion.entregado_en)
        self.assertEqual(
            self.perfil_repartidor.estado_actual,
            PerfilRepartidor.EstadoActual.DISPONIBLE,
        )
        self.assertTrue(
            HistorialEntrega.objects.filter(
                pedido=self.pedido,
                repartidor=self.repartidor,
                evento=HistorialEntrega.EventoEntrega.ENTREGADO,
            ).exists()
        )

    def test_otro_repartidor_no_puede_modificar_pedido_ajeno(self):
        self.client_api.force_authenticate(user=self.otro_repartidor)

        response = self.client_api.post(
            reverse("logistica:confirmar_recojo", args=[self.pedido.id]),
            {"observacion": "Intento no autorizado."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("otro repartidor", response.json()["detail"].lower())
