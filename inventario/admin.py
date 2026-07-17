from django.contrib import admin
from .models import Persona, OrdenTrabajo, Asignacion


class AsignacionInline(admin.TabularInline):
    model = Asignacion
    extra = 1
    autocomplete_fields = ['persona']


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'apellido', 'email', 'telefono', 'activo', 'fecha_creacion']
    list_filter = ['activo']
    search_fields = ['nombre', 'apellido', 'email', 'telefono']
    ordering = ['apellido', 'nombre']


@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ['numero_orden', 'fecha', 'completada', 'total_acciones', 'total_horas', 'cantidad_personas']
    list_filter = ['completada', 'fecha']
    search_fields = ['numero_orden', 'descripcion']
    inlines = [AsignacionInline]


@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ['orden_trabajo', 'persona', 'fecha', 'acciones', 'horas_diurnas', 'horas_extras']
    list_filter = ['fecha']
    search_fields = ['orden_trabajo__numero_orden', 'persona__nombre', 'persona__apellido']
    autocomplete_fields = ['orden_trabajo', 'persona']
