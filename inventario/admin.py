from django.contrib import admin
from .models import Persona, OrdenTrabajo, Asignacion, ParteTrabajo, PartePersona, Equipo


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
    list_display = ['numero_orden', 'fecha', 'completada', 'cantidad_personas']
    list_filter = ['completada', 'fecha']
    search_fields = ['numero_orden', 'descripcion']
    inlines = [AsignacionInline]


@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ['orden_trabajo', 'persona', 'fecha', 'acciones', 'horas_diurnas', 'horas_extras']
    list_filter = ['fecha']
    search_fields = ['orden_trabajo__numero_orden', 'persona__nombre', 'persona__apellido']
    autocomplete_fields = ['orden_trabajo', 'persona']


class PartePersonaInline(admin.TabularInline):
    model = PartePersona
    extra = 1
    autocomplete_fields = ['persona']


@admin.register(ParteTrabajo)
class ParteTrabajoAdmin(admin.ModelAdmin):
    list_display = ['pk', 'fecha_inicio', 'fecha_fin', 'acciones', 'cantidad_equipos', 'total_acciones', 'creado_por']
    list_filter = ['fecha_inicio', 'fecha_fin']
    search_fields = ['pk']
    inlines = [PartePersonaInline]


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ['municipio', 'unidad_salud', 'denominacion', 'marca', 'modelo', 'estado']
    list_filter = ['municipio', 'tipo', 'estado']
    search_fields = ['municipio', 'unidad_salud', 'marca', 'modelo', 'numero_serie']


@admin.register(PartePersona)
class PartePersonaAdmin(admin.ModelAdmin):
    list_display = ['parte', 'persona', 'horas_trabajadas', 'horas_extras']
    list_filter = ['parte__fecha_inicio']
    search_fields = ['persona__nombre', 'persona__apellido']
    autocomplete_fields = ['persona']
    raw_id_fields = ['parte']
