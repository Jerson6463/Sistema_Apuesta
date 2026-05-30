from django.contrib import admin

from wallet.models import EntradaContable


@admin.register(EntradaContable)
class EntradaContableAdmin(admin.ModelAdmin):
    list_display = (
        "id_transaccion", "cuenta", "usuario", "monto", "direccion",
        "tipo_referencia", "creado_en",
    )
    list_filter = ("cuenta", "direccion", "tipo_referencia")
    search_fields = ("usuario__username", "id_transaccion")
    readonly_fields = (
        "id", "cuenta", "usuario", "monto", "direccion",
        "id_transaccion", "tipo_referencia", "referencia_id", "creado_en",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
