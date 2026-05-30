from django.contrib import admin
from django.db.models import Sum

from betting.models import (
    Apuesta, ApuestaCombinada, Cuota, Evento, HistorialCuota, Mercado,
)
from betting.services import liquidar_apuesta, anular_apuesta


class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 0
    fields = ("seleccion", "valor", "activa")


class MercadoInline(admin.TabularInline):
    model = Mercado
    extra = 0
    fields = ("tipo", "estado", "monto_minimo", "monto_maximo")
    show_change_link = True


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "deporte", "equipo_local", "equipo_visitante", "fecha_inicio", "estado")
    list_filter = ("estado", "deporte")
    search_fields = ("nombre", "equipo_local", "equipo_visitante")
    inlines = [MercadoInline]
    actions = ["accion_iniciar", "accion_finalizar", "accion_anular"]

    @admin.action(description="Iniciar eventos seleccionados")
    def accion_iniciar(self, request, queryset):
        for evento in queryset:
            try:
                evento.iniciar()
                evento.save()
            except Exception:
                pass

    @admin.action(description="Finalizar eventos seleccionados")
    def accion_finalizar(self, request, queryset):
        for evento in queryset:
            try:
                evento.finalizar()
                evento.save()
            except Exception:
                pass

    @admin.action(description="Anular eventos seleccionados")
    def accion_anular(self, request, queryset):
        for evento in queryset:
            try:
                evento.anular()
                evento.save()
            except Exception:
                pass


@admin.register(Mercado)
class MercadoAdmin(admin.ModelAdmin):
    list_display = ("evento", "tipo", "estado", "monto_minimo", "monto_maximo")
    list_filter = ("tipo", "estado")
    inlines = [CuotaInline]


@admin.register(Apuesta)
class ApuestaAdmin(admin.ModelAdmin):
    list_display = (
        "id", "usuario", "estado", "monto_apostado",
        "cuota_al_apostar", "pago_potencial", "creado_en",
    )
    list_filter = ("estado",)
    search_fields = ("usuario__username", "id")
    readonly_fields = (
        "id", "usuario", "cuota", "monto_apostado", "cuota_al_apostar",
        "pago_potencial", "clave_idempotencia", "ip_origen", "creado_en",
    )
