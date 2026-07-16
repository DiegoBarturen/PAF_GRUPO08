# pedidos/email_service.py
"""
Servicio de notificaciones por email para el flujo de pedidos.
Usa Django's email backend — compatible con Resend SMTP o console (desarrollo).

PARA ACTIVAR RESEND EN PRODUCCIÓN:
  1. Crea cuenta en resend.com (gratis)
  2. Ve a Settings → API Keys → Create API Key
  3. En config/settings.py cambia:

       EMAIL_BACKEND   = 'django.core.mail.backends.smtp.EmailBackend'
       EMAIL_HOST      = 'smtp.resend.com'
       EMAIL_PORT      = 465
       EMAIL_USE_SSL   = True
       EMAIL_HOST_USER = 'resend'
       EMAIL_HOST_PASSWORD = 're_TU_API_KEY_AQUI'
       DEFAULT_FROM_EMAIL  = 'noreply@tudominio.com'

  Si no tienes dominio propio puedes usar:
       DEFAULT_FROM_EMAIL  = 'onboarding@resend.dev'
  (Solo para pruebas — Resend te da este remitente de sandbox gratis)
"""

from django.core.mail import send_mail
from django.conf import settings


def _get_from_email():
    """Devuelve el remitente configurado o un fallback."""
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@deliverynativo.com')


def enviar_confirmacion_pedido(pedido):
    """
    Email #1 — Se envía cuando el cliente hace un pedido exitosamente.
    Contiene: número de pedido, sede, ítems, totales y método de pago.
    """
    try:
        if not pedido.cliente.email:
            return  # Sin correo → silenciosamente no enviamos

        # Construir la lista de ítems en texto plano
        items_texto = ""
        for item in pedido.items_pedido.select_related('producto').all():
            items_texto += f"  • {item.cantidad}x {item.producto.nombre}  →  S/ {item.precio_unitario * item.cantidad:.2f}\n"

        descuento_texto = f"  Descuento cupón:  - S/ {pedido.descuento:.2f}\n" if pedido.descuento > 0 else ""

        asunto = f"✅ Pedido #{pedido.id} confirmado — Delivery NATIVO"

        cuerpo = f"""
¡Hola, {pedido.cliente.get_full_name() or pedido.cliente.username}! 👋

Tu pedido ha sido recibido con éxito. Aquí está el resumen:

━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🛵 DELIVERY NATIVO
  Pedido #{pedido.id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏪 Local:      {pedido.sede.negocio.nombre_comercial} — {pedido.sede.nombre}
📍 Entrega en: {pedido.direccion_entrega}
📞 Teléfono:   {pedido.telefono or 'No especificado'}

─── TU ORDEN ──────────────────────
{items_texto}
─────────────────────────────────
  Subtotal productos:  S/ {pedido.subtotal:.2f}
{descuento_texto}  Costo de envío:      S/ {pedido.costo_envio:.2f}
  ─────────────────────────────
  TOTAL A PAGAR:       S/ {pedido.total:.2f}
─────────────────────────────────

💳 Método de pago: {pedido.get_metodo_pago_display()}
📝 Observaciones: {pedido.observaciones or 'Ninguna'}

Puedes ver el estado de tu pedido en cualquier momento ingresando
a tu historial en Delivery NATIVO.

¡Gracias por tu preferencia! 🙏
El equipo de Delivery NATIVO
        """.strip()

        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=_get_from_email(),
            recipient_list=[pedido.cliente.email],
            fail_silently=True,  # Si falla el email, el pedido ya está guardado, no interrumpir
        )

    except Exception:
        pass  # El email es opcional — nunca debe romper el flujo del pedido


def enviar_notificacion_en_camino(pedido):
    """
    Email #2 — Se envía cuando el negocio cambia el estado a 'En Camino'.
    Avisa al cliente que el repartidor ya salió.
    """
    try:
        if not pedido.cliente.email:
            return

        asunto = f"🛵 Tu pedido #{pedido.id} está en camino — Delivery NATIVO"

        cuerpo = f"""
¡Buenas noticias, {pedido.cliente.get_full_name() or pedido.cliente.username}! 🎉

Tu repartidor ya salió con tu pedido y se dirige a tu dirección.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Pedido #{pedido.id}
  🏪 {pedido.sede.negocio.nombre_comercial}
  📍 Entregando en: {pedido.direccion_entrega}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Por favor, mantente disponible en tu dirección de entrega.

¡Buen provecho! 🍽️
El equipo de Delivery NATIVO
        """.strip()

        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=_get_from_email(),
            recipient_list=[pedido.cliente.email],
            fail_silently=True,
        )

    except Exception:
        pass


def enviar_notificacion_entregado(pedido):
    """
    Email #3 — Se envía cuando el pedido es marcado como 'Entregado'.
    Invita al cliente a dejar una valoración.
    """
    try:
        if not pedido.cliente.email:
            return

        asunto = f"🏁 Pedido #{pedido.id} entregado — ¿Cómo estuvo? — Delivery NATIVO"

        cuerpo = f"""
¡Hola, {pedido.cliente.get_full_name() or pedido.cliente.username}!

Tu pedido #{pedido.id} de {pedido.sede.negocio.nombre_comercial} ha sido entregado exitosamente. 🎉

Esperamos que lo hayas disfrutado. Tu opinión es muy importante para nosotros
y para el local. ¡Puedes dejar tu valoración desde tu historial de pedidos!

Total pagado: S/ {pedido.total:.2f}

Gracias por elegir Delivery NATIVO. ¡Hasta la próxima! 🛵
El equipo de Delivery NATIVO
        """.strip()

        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=_get_from_email(),
            recipient_list=[pedido.cliente.email],
            fail_silently=True,
        )

    except Exception:
        pass
