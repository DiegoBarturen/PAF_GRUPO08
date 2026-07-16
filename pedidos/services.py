from decimal import Decimal
from django.db import transaction
from catalogo.models import Producto, Sede
from pedidos.models import Pedido, ItemPedido
from pedidos.exceptions import ProductoSinStock, CarritoVacio, TransicionInvalida
from logistica.services import asignar_repartidor_a_pedido
from config.choices import EstadoPedido

class PedidoService:
    @staticmethod
    @transaction.atomic
    def procesar_pedido(cliente, carrito, form_data, cupon_aplicado):
        if not carrito:
            raise CarritoVacio("El carrito está vacío.")

        productos_carrito = []
        sede_id = None
        subtotal_temp = Decimal("0.00")

        # Preparar y validar productos (sin bloquear aún)
        for str_id, datos_item in carrito.items():
            producto = Producto.objects.select_related("sede").get(id=datos_item["producto_id"])
            cantidad = int(datos_item["cantidad"])
            productos_carrito.append((producto, cantidad))

            if sede_id is None:
                sede_id = producto.sede_id
            elif sede_id != producto.sede_id:
                raise ValueError("El carrito contiene productos de distintas sedes.")

            precio_a_usar = producto.precio_oferta if (producto.precio_oferta and producto.precio_oferta > 0) else producto.precio
            subtotal_temp += Decimal(str(precio_a_usar)) * Decimal(str(cantidad))

        if not productos_carrito:
            raise CarritoVacio("No se encontraron productos válidos en el carrito.")

        sede = productos_carrito[0][0].sede
        costo_envio = sede.costo_envio or Decimal("0.00")
        
        # Descuento
        descuento = Decimal("0.00")
        if cupon_aplicado == "NATIVO25":
            if not Pedido.objects.filter(cliente=cliente).exists():
                descuento = (subtotal_temp * Decimal("0.25")).quantize(Decimal("0.01"))

        subtotal = subtotal_temp.quantize(Decimal("0.01"))
        total = (subtotal_temp - descuento + costo_envio).quantize(Decimal("0.01"))

        # Crear pedido
        pedido = Pedido(
            cliente=cliente,
            sede=sede,
            telefono=form_data.get("telefono"),
            metodo_pago=form_data.get("metodo_pago"),
            direccion_entrega=form_data.get("direccion_entrega"),
            observaciones=form_data.get("observaciones", ""),
            latitud=form_data.get("latitud"),
            longitud=form_data.get("longitud"),
            costo_envio=costo_envio,
            subtotal=subtotal,
            descuento=descuento,
            total=total
        )
        if descuento > 0:
            pedido.cupon = "NATIVO25"
        pedido.save()

        # Descontar stock atómicamente y crear items
        for producto_base, cantidad in productos_carrito:
            producto = Producto.objects.select_for_update().get(id=producto_base.id)

            if producto.stock < cantidad:
                raise ProductoSinStock(f"Stock insuficiente para el producto: {producto.nombre}")

            producto.stock -= cantidad
            producto.save(update_fields=["stock", "actualizado_en"])

            ItemPedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=producto.precio
            )

        return pedido

    @staticmethod
    def cambiar_estado(pedido, nuevo_estado):
        estados_validos = dict(EstadoPedido.choices)
        if nuevo_estado not in estados_validos:
            raise TransicionInvalida(f"'{nuevo_estado}' no es un estado válido.")
            
        pedido.estado = nuevo_estado
        pedido.save(update_fields=["estado", "actualizado_en"])

        # Lógica de asignación al cambiar a LISTO_RECOJO
        asignacion = None
        if nuevo_estado == EstadoPedido.LISTO_RECOJO:
            asignacion = asignar_repartidor_a_pedido(pedido)
            
        return pedido, asignacion
