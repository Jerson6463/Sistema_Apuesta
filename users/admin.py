from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from users.models import Usuario, LimiteJuego, AutoExclusion


class LimiteJuegoInline(admin.StackedInline):
    model = LimiteJuego
    can_delete = False
    verbose_name_plural = "Límites de juego"


class AutoExclusionInline(admin.TabularInline):
    model = AutoExclusion
    extra = 0
    readonly_fields = ("fecha_inicio", "fecha_fin", "tipo")
    can_delete = False


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    inlines = [LimiteJuegoInline, AutoExclusionInline]
    list_display = ("username", "email", "dni", "estado", "is_active", "date_joined")
    list_filter = ("estado", "is_active")
    search_fields = ("username", "email", "dni")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Datos KYC",
            {"fields": ("dni", "fecha_nacimiento", "estado")},
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Datos KYC",
            {"fields": ("dni", "fecha_nacimiento")},
        ),
    )


@admin.register(AutoExclusion)
class AutoExclusionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "fecha_inicio", "fecha_fin", "esta_activa")
    list_filter = ("tipo",)
    readonly_fields = ("fecha_inicio",)
