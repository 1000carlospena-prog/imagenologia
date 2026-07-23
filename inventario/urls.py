from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('personas/', views.persona_list, name='persona_list'),
    path('personas/nueva/', views.persona_create, name='persona_create'),
    path('personas/<int:pk>/editar/', views.persona_update, name='persona_update'),
    path('personas/<int:pk>/eliminar/', views.persona_delete, name='persona_delete'),

    path('ordenes/', views.orden_list, name='orden_list'),
    path('ordenes/nueva/', views.orden_create, name='orden_create'),
    path('ordenes/<int:pk>/', views.orden_detail, name='orden_detail'),
    path('ordenes/<int:pk>/editar/', views.orden_update, name='orden_update'),
    path('ordenes/<int:pk>/eliminar/', views.orden_delete, name='orden_delete'),

    path('asignacion/<int:pk>/eliminar/', views.asignacion_delete, name='asignacion_delete'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('select-persona/', views.select_persona, name='select_persona'),
    path('generar-orden/', views.generar_orden, name='generar_orden'),
    path('partes/<int:pk>/eliminar/', views.parte_delete, name='parte_delete'),
    path('equipos/', views.equipo_list, name='equipo_list'),
    path('equipos/nuevo/', views.equipo_create, name='equipo_create'),
    path('equipos/<int:pk>/editar/', views.equipo_update, name='equipo_update'),
    path('equipos/<int:pk>/eliminar/', views.equipo_delete, name='equipo_delete'),
    path('equipos/duplicados/', views.equipo_duplicados, name='equipo_duplicados'),
    path('historial/', views.historial, name='historial'),
]
