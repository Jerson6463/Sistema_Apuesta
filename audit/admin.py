from django.contrib import admin
from django.utils import timezone

from audit.models import ActividadSospechosa, RegistroAuditoria
from audit.services import verificar_integridad_cadena


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("tipo_evento", "hash_actual_corto", "hash_anterior_corto", "usuario", "creado_en")
    list_filter = ("tipo_evento",)
    search_fields = ("hash_actual", "usuario__username")
    readonly_fields = (
        "id", "tipo_evento", "payload", "hash_anterior",
        "hash_actual", "usuario", "creado_en",
    )

    def hash_actual_corto(self, obj):
        return obj.hash_actual[:16] + "…"
    hash_actual_corto.short_description = "Hash actual"

    def hash_anterior_corto(self, obj):
        return obj.hash_anterior[:16] + "…"
    hash_anterior_corto.short_description = "Hash anterior"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    actions = ["accion_verificar_integridad"]

    @admin.action(description="Verificar integridad de la cadena de hash")
    def accion_verificar_integridad(self, request, queryset):
        es_valida, errores = verificar_integridad_cadena()
        if es_valida:
            self.message_user(request, "Cadena de auditoría íntegra. Todos los hashes son válidos.")
        else:
            for error in errores:
                self.message_user(request, f"ERROR: {error}", level="error")


@admin.register(ActividadSospechosa)
class ActividadSospechosaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo_alerta", "revisado", "creado_en")
    list_filter = ("tipo_alerta", "revisado")
    search_fields = ("usuario__username", "descripcion")
    readonly_fields = ("usuario", "tipo_alerta", "descripcion", "creado_en")
    actions = ["marcar_revisado"]

    @admin.action(description="Marcar como revisado")
    def marcar_revisado(self, request, queryset):
        queryset.update(revisado=True, revisado_por=request.user, revisado_en=timezone.now())
