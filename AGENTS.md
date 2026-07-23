# Imagenología — Inventory Management System

## Tech Stack
- **Framework:** Django 4.2+ (Python)
- **Database:** SQLite (dev) / PostgreSQL (production, via Render)
- **Frontend:** Bootstrap 5.3.3, Bootstrap Icons, Chart.js
- **Static files:** WhiteNoise
- **Server:** Gunicorn
- **Deploy:** Render (Blueprint via `render.yaml` + manual Web Service)

## Project Structure
```
imagenologia/                  # Django project config
├── settings.py               # Main settings (DB, auth, static/media)
├── urls.py                   # Root URL routing
├── wsgi.py / asgi.py         # WSGI/ASGI entry points
inventario/                   # Main app
├── models.py                 # 6 models
├── views.py                  # All views (function-based)
├── urls.py                   # App URL routes
├── forms.py                  # ModelForms with Bootstrap widgets
├── admin.py                  # Admin config with inlines
├── apps.py                   # App config
├── context_processors.py     # persona_actual for navbar
├── management/commands/
│   ├── createsu.py           # Create superuser
│   └── importar_equipos.py   # Import equipos from Excel
├── migrations/               # 7 migrations
├── templatetags/
│   └── inventario_tags.py    # Custom template tags/filters
├── templates/inventario/     # 14 HTML templates
└── static/inventario/
    ├── css/style.css         # Custom styles
    └── js/main.js            # Alert auto-dismiss (5s)
data/                         # Excel files for equipment import
media/                        # User-uploaded files (gitignored)
venv/                         # Virtual environment (gitignored)
```

## Authentication Flow
1. **Login** (`/login/`) — Django auth (user: `rximagenologia`, pass: `59968839`)
2. **Select persona** (`/select-persona/`) — elige quién eres (Carlos Peña, Rafael Castillo, Carlos Medina), con botón "Usuario nuevo" para añadir persona rápida
3. **Dashboard** (`/`) — resumen del mes actual por persona (acciones, horas trabajadas, horas extra)

## Models & Relationships
```
Persona ──< Asignacion >── OrdenTrabajo    (legacy)
Persona ──< PartePersona >── ParteTrabajo  (current)
Equipo                                       (inventory)
```
- **Persona:** nombre, apellido, email, telefono, activo
- **OrdenTrabajo:** numero_orden (unique), descripcion, fecha, completada
- **Asignacion:** FK → Persona + OrdenTrabajo, fecha, acciones, horas_diurnas, horas_extras; `unique_together=[orden_trabajo, persona, fecha]`
- **ParteTrabajo:** fecha_inicio, fecha_fin, acciones (1-10), cantidad_equipos, total_acciones, creado_por (FK Persona), fecha_creacion
- **PartePersona:** FK → ParteTrabajo + Persona, horas_trabajadas, horas_extras; `unique_together=[parte, persona]`
- **Equipo:** municipio, unidad_salud, tipo (RX/USD/OTRO), denominacion, servicio, local, marca, modelo, numero_serie, estado (texto libre), observaciones, frecuencia, fuente, fecha_creacion

## URL Routes
| Prefix | Views | Names |
|--------|-------|-------|
| `/` | dashboard | `dashboard` |
| `/login/` | login | `login` |
| `/logout/` | logout | `logout` |
| `/select-persona/` | persona selection | `select_persona` |
| `/generar-orden/` | create work order | `generar_orden` |
| `/personas/` | list, create, update, delete | `persona_*` |
| `/ordenes/` | list, create, detail, update, delete | `orden_*` |
| `/asignacion/<pk>/eliminar/` | delete | `asignacion_delete` |
| `/equipos/` | list with filters | `equipo_list` |
| `/equipos/nuevo/` | create | `equipo_create` |
| `/equipos/<pk>/editar/` | update | `equipo_update` |
| `/equipos/<pk>/eliminar/` | delete | `equipo_delete` |
| `/admin/` | Django admin | — |

## Equipment Import System
- 4 Excel files in `data/` directory (imported from `C:\Users\Carlos\Desktop\exel\`)
- Run: `python manage.py importar_equipos` (skips if data exists) or `--force` to re-import
- Files: RX Provincia x marca, USD x Marcas, USD x Municipios, Plan de Mtto
- USD x Municipios uses dynamic header detection (varies per sheet)
- ~462 equipos imported total

## Forms
- `EquipoForm`: all fields editable, `estado` uses TextInput with HTML5 datalist for suggestions from existing values
- `ParteTrabajoForm`: CheckboxSelectMultiple for personas, global horas_trabajadas/horas_extras fields
- Filters on equipo_list: marca, modelo, unidad_salud, municipio, estado — all populated with distinct DB values

## Environment Variables
| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key (required) |
| `DJANGO_DEBUG` | `True`/`False` (default: `True`) |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated (default: `localhost,127.0.0.1`) |
| `DB_ENGINE` | DB backend (default: sqlite3) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL (optional) |
| `DJANGO_SU_USER` | Superuser username (default: `1000carlos`) |
| `DJANGO_SU_EMAIL` | Superuser email |
| `DJANGO_SU_PASSWORD` | Superuser password |

## Development
```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py importar_equipos --force
python manage.py createsu --password=micontraseña
python manage.py runserver
```

## Deployment (Render)
- **URL:** `https://rximagenologiastgo.onrender.com`
- **Admin:** user `rximagenologia`, password `59968839`
- **DB:** Uses existing PostgreSQL from `cmpf` project (`cmpf-db`)
- **Deploy Hook:** `https://api.render.com/deploy/srv-d9go22svikkc739q7nb0?key=GByPRq7pM-Y`
- **Procfile:** `web: python manage.py migrate && python manage.py importar_equipos && gunicorn ...`
- **render.yaml** defines web service + PostgreSQL database
- Build runs `collectstatic --noinput`, static via WhiteNoise
- After first deploy with `--force`, remove flag to preserve manual edits

## Conventions
- **Language:** Spanish (es-mx), Mexico City timezone
- **Templates:** Bootstrap 5 with `container-fluid`, responsive tables
- **Forms:** `ModelForm` with explicit `widgets` using Bootstrap classes
- **Messages:** Django contrib messages with Bootstrap alerts (auto-dismiss 5s)
- **Pagination:** `Paginator` with 20 items/page, preserved query params
- **Aggregations:** `annotate()` + `Sum`/`Count` for computed totals (avoid N+1)
- **CSS/HTML separated**, endpoints preserved, backwards-compatible migrations
- **No REST API** — everything server-side rendered
