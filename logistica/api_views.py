from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.choices import EstadoPedido
from pedidos.models import Pedido

from .models import AsignacionPedido, HistorialEntrega, PerfilRepartidor
from .services import asignar_siguiente_pedido_disponible_a_repartidor
from .serializers import (
    ActualizarPerfilRepartidorSerializer,
    ActualizarUbicacionSerializer,
    EstadoPedidoLogisticoSerializer,
    HistorialEntregaSerializer,
    PedidoActivoSerializer,
    PerfilRepartidorSerializer,
    ResumenOperativoSerializer,
)


class RepartidorRequiredMixin:
    permission_classes = [IsAuthenticated]

    def validate_repartidor(self, request, repartidor_id=None):
        if getattr(request.user, "rol", None) != "repartidor":
            return Response(
                {"detail": "Solo los usuarios con rol repartidor pueden usar este endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if repartidor_id is not None and request.user.id != repartidor_id:
            return Response(
                {"detail": "No puedes modificar la ubicacion de otro repartidor."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return None

    def get_asignacion_activa(self, pedido_id, repartidor):
        asignacion = (
            AsignacionPedido.objects.select_related("pedido", "repartidor")
            .filter(pedido_id=pedido_id, activa=True)
            .first()
        )

        if not asignacion:
            pedido = (
                Pedido.objects.select_related("repartidor")
                .filter(
                    pk=pedido_id,
                    repartidor=repartidor,
                    estado__in=[EstadoPedido.LISTO_RECOJO, EstadoPedido.EN_CAMINO],
                )
                .first()
            )

            if not pedido:
                return None, Response(
                    {"detail": "No existe una asignacion activa para este pedido."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            asignacion_existente = (
                AsignacionPedido.objects.select_related("pedido", "repartidor")
                .filter(pedido=pedido)
                .first()
            )

            if asignacion_existente:
                if asignacion_existente.repartidor_id != repartidor.id:
                    return None, Response(
                        {"detail": "No puedes modificar un pedido asignado a otro repartidor."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                if not asignacion_existente.activa:
                    asignacion_existente.activa = True
                    asignacion_existente.save(update_fields=["activa"])

                asignacion = asignacion_existente
            else:
                asignacion = AsignacionPedido.objects.create(
                    pedido=pedido,
                    repartidor=repartidor,
                )
                HistorialEntrega.objects.create(
                    pedido=pedido,
                    repartidor=repartidor,
                    evento=HistorialEntrega.EventoEntrega.ASIGNADO,
                    observacion=(
                        "Asignacion activa reconstruida automaticamente para continuar la ruta."
                    ),
                )

        if asignacion.repartidor_id != repartidor.id:
            return None, Response(
                {"detail": "No puedes modificar un pedido asignado a otro repartidor."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return asignacion, None

    def get_asignacion_activa_repartidor(self, repartidor):
        return (
            AsignacionPedido.objects.select_related("pedido")
            .filter(repartidor=repartidor, activa=True)
            .order_by("-asignado_en")
            .first()
        )

    def intentar_autoasignacion(self, repartidor):
        try:
            return asignar_siguiente_pedido_disponible_a_repartidor(repartidor), None
        except Exception as exc:
            return None, str(exc)


class ActualizarUbicacionRepartidorView(RepartidorRequiredMixin, APIView):
    def post(self, request, repartidor_id):
        permission_error = self.validate_repartidor(request, repartidor_id=repartidor_id)
        if permission_error:
            return permission_error

        serializer = ActualizarUbicacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)
        perfil.latitud = serializer.validated_data["latitud"]
        perfil.longitud = serializer.validated_data["longitud"]
        perfil.ultima_actualizacion_ubicacion = timezone.now()
        perfil.save()

        asignacion_auto_error = None
        if perfil.estado_actual == PerfilRepartidor.EstadoActual.DISPONIBLE:
            _, asignacion_auto_error = self.intentar_autoasignacion(request.user)

        response_data = {
            "message": "Ubicacion actualizada correctamente.",
            "repartidor_id": request.user.id,
            "latitud": str(perfil.latitud),
            "longitud": str(perfil.longitud),
            "actualizado_en": perfil.ultima_actualizacion_ubicacion.isoformat(),
        }
        if asignacion_auto_error:
            response_data["warning"] = (
                "La ubicacion se actualizo, pero no se pudo intentar la autoasignacion."
            )

        return Response(response_data, status=status.HTTP_200_OK)


class MiPedidoActivoApiView(RepartidorRequiredMixin, APIView):
    def get(self, request):
        permission_error = self.validate_repartidor(request)
        if permission_error:
            return permission_error

        asignacion = (
            AsignacionPedido.objects.select_related(
                "pedido",
                "pedido__cliente",
                "pedido__negocio",
                "repartidor",
            )
            .filter(repartidor=request.user, activa=True)
            .first()
        )

        if not asignacion:
            return Response(
                {"detail": "No tienes un pedido activo asignado en este momento."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PedidoActivoSerializer(asignacion)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MiPerfilRepartidorApiView(RepartidorRequiredMixin, APIView):
    def get(self, request):
        permission_error = self.validate_repartidor(request)
        if permission_error:
            return permission_error

        perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)
        serializer = PerfilRepartidorSerializer(perfil)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        permission_error = self.validate_repartidor(request)
        if permission_error:
            return permission_error

        perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)
        serializer = ActualizarPerfilRepartidorSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        asignacion_activa = self.get_asignacion_activa_repartidor(request.user)
        nuevo_estado = serializer.validated_data.get("estado_actual")

        if nuevo_estado == PerfilRepartidor.EstadoActual.INACTIVO and asignacion_activa:
            return Response(
                {
                    "detail": (
                        "No puedes pasar a inactivo mientras tengas un pedido activo asignado. "
                        "Completa o libera tu ruta primero."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field, value in serializer.validated_data.items():
            setattr(perfil, field, value)

        perfil.save()

        asignacion_auto_error = None
        if perfil.estado_actual == PerfilRepartidor.EstadoActual.DISPONIBLE:
            _, asignacion_auto_error = self.intentar_autoasignacion(request.user)

        response_serializer = PerfilRepartidorSerializer(perfil)
        response_data = dict(response_serializer.data)
        if asignacion_auto_error:
            response_data["warning"] = (
                "El perfil se actualizo, pero no se pudo intentar la autoasignacion."
            )
        return Response(response_data, status=status.HTTP_200_OK)


class MiHistorialEntregasApiView(RepartidorRequiredMixin, APIView):
    def get(self, request):
        permission_error = self.validate_repartidor(request)
        if permission_error:
            return permission_error

        historial = HistorialEntrega.objects.filter(repartidor=request.user).select_related("pedido", "repartidor")
        serializer = HistorialEntregaSerializer(historial, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MiResumenOperativoApiView(RepartidorRequiredMixin, APIView):
    def get(self, request):
        permission_error = self.validate_repartidor(request)
        if permission_error:
            return permission_error

        perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)
        asignacion_activa = (
            AsignacionPedido.objects.filter(repartidor=request.user, activa=True)
            .order_by("-asignado_en")
            .first()
        )
        resumen = {
            "repartidor": request.user.username,
            "estado_actual": perfil.get_estado_actual_display(),
            "vehiculo": perfil.vehiculo,
            "pedido_activo_id": asignacion_activa.pedido_id if asignacion_activa else None,
            "total_asignaciones": AsignacionPedido.objects.filter(repartidor=request.user).count(),
            "total_entregas_completadas": HistorialEntrega.objects.filter(
                repartidor=request.user,
                evento=HistorialEntrega.EventoEntrega.ENTREGADO,
            ).count(),
            "total_historial_eventos": HistorialEntrega.objects.filter(repartidor=request.user).count(),
        }
        serializer = ResumenOperativoSerializer(resumen)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConfirmarRecojoView(RepartidorRequiredMixin, APIView):
    def post(self, request, pedido_id):
        permission_error = self.validate_repartidor(request)
        if permission_error:
            return permission_error

        serializer = EstadoPedidoLogisticoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        asignacion, error_response = self.get_asignacion_activa(
            pedido_id=pedido_id,
            repartidor=request.user,
        )
        if error_response:
            return error_response
        pedido = asignacion.pedido

        if pedido.estado != EstadoPedido.LISTO_RECOJO:
            return Response(
                {"detail": "El pedido debe estar en estado 'Listo para recojo' para confirmar el recojo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pedido.estado = EstadoPedido.EN_CAMINO
        pedido.repartidor = request.user
        pedido.save(update_fields=["estado", "repartidor", "fecha_actualizacion"])

        asignacion.marcar_recogido()

        perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)
        perfil.estado_actual = PerfilRepartidor.EstadoActual.EN_RUTA
        perfil.save(update_fields=["estado_actual"])

        HistorialEntrega.objects.create(
            pedido=pedido,
            repartidor=request.user,
            evento=HistorialEntrega.EventoEntrega.RECOGIDO,
            observacion=serializer.validated_data.get("observacion", ""),
        )

        return Response(
            {
                "message": "Recojo confirmado correctamente.",
                "pedido_id": pedido.id,
                "estado": pedido.estado,
                "estado_display": pedido.get_estado_display(),
                "recogido_en": asignacion.recogido_en.isoformat() if asignacion.recogido_en else None,
            },
            status=status.HTTP_200_OK,
        )


class ConfirmarEntregaView(RepartidorRequiredMixin, APIView):
    def post(self, request, pedido_id):
        permission_error = self.validate_repartidor(request)
        if permission_error:
            return permission_error

        serializer = EstadoPedidoLogisticoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        asignacion, error_response = self.get_asignacion_activa(
            pedido_id=pedido_id,
            repartidor=request.user,
        )
        if error_response:
            return error_response
        pedido = asignacion.pedido

        if pedido.estado != EstadoPedido.EN_CAMINO:
            return Response(
                {"detail": "El pedido debe estar en estado 'En camino' para confirmar la entrega."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pedido.estado = EstadoPedido.ENTREGADO
        pedido.repartidor = request.user
        pedido.save(update_fields=["estado", "repartidor", "fecha_actualizacion"])

        asignacion.marcar_entregado()

        HistorialEntrega.objects.create(
            pedido=pedido,
            repartidor=request.user,
            evento=HistorialEntrega.EventoEntrega.ENTREGADO,
            observacion=serializer.validated_data.get("observacion", ""),
        )

        perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)
        perfil.estado_actual = PerfilRepartidor.EstadoActual.DISPONIBLE
        perfil.save(update_fields=["estado_actual"])

        siguiente_asignacion, asignacion_auto_error = self.intentar_autoasignacion(request.user)

        response_data = {
            "message": "Entrega confirmada correctamente.",
            "pedido_id": pedido.id,
            "estado": pedido.estado,
            "estado_display": pedido.get_estado_display(),
            "entregado_en": asignacion.entregado_en.isoformat() if asignacion.entregado_en else None,
            "siguiente_pedido_id": (
                siguiente_asignacion.pedido_id if siguiente_asignacion else None
            ),
        }
        if asignacion_auto_error:
            response_data["warning"] = (
                "La entrega se confirmo, pero no se pudo autoasignar el siguiente pedido."
            )

        return Response(response_data, status=status.HTTP_200_OK)
