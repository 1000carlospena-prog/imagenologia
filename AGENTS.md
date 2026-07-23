# Imagenología — Inventory Management System

## Tech Stack
- **Framework:** Django 4.2+ (Python)
- **Database:** SQLite (dev) / PostgreSQL (production, via Render)
- **Frontend:** Bootstrap 5.3.3, Bootstrap Icons, Chart.js
- **Static files:** WhiteNoise
- **Server:** Gunicorn
- **Deploy:** Render (see `render.yaml`)

## Project Structure
```
imagenologia/                  # Django project config
├── settings.py               # Main settings (DB, auth, static/media)
├── urls.py                   # Root URL routing
├── wsgi.py / asgi.py         # WSGI/ASGI entry points
inventario/                   # Main app
├── models.py                 # Persona, OrdenTrabajo, Asignacion
├── views.py                  # All views (function-based)
├── urls.py                   # App URL routes
├── forms.py                  # ModelForms with Bootstrap widgets
├── admin.py                  # Admin config with inlines
├── apps.py                   # App config
├── management/commands/
│   └── createsu.py           # Custom command to create superuser
├── migrations/
│   └── 0001_initial.py       # Initial schema
├── templatetags/
│   └── inventario_tags.py    # Custom template tags/filters
├── templates/inventario/     # 10 HTML templates
├── static/inventario/
│   ├── css/style.css         # Custom styles
│   └── js/main.js            # Alert auto-dismiss (5s)
media/                        # User-uploaded files (gitignored)
venv/                         # Virtual environment (gitignored)
```

## Models & Relationships
```
Persona ──< Asignacion >── OrdenTrabajo
```
- **Persona:** nombre, apellido, email, telefono, activo
- **OrdenTrabajo:** numero_orden (unique), descripcion, fecha, completada
- **Asignacion:** FK → Persona + OrdenTrabajo, fecha, acciones, horas_diurnas, horas_extras
- `unique_together = [orden_trabajo, persona, fecha]` — one entry per person per order per day

## URL Routes
| Prefix | Views | Names |
|--------|-------|-------|
| `/` | dashboard | `dashboard` |
| `/personas/` | list, create, update, delete | `persona_*` |
| `/ordenes/` | list, create, detail, update, delete | `orden_*` |
| `/asignacion/<pk>/eliminar/` | delete | `asignacion_delete` |
| `/admin/` | Django admin | — |

All views are function-based. Templates extend `base.html`.

## Environment Variables (required)
| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key (required, no fallback) |
| `DJANGO_DEBUG` | `True`/`False` (defaults to `True`) |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts (default: `localhost,127.0.0.1`) |
| `DB_ENGINE` | DB backend (default: sqlite3) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL connection (optional; fallback to sqlite3) |
| `DJANGO_SU_USER` | Superuser username for `createsu` (default: `1000carlos`) |
| `DJANGO_SU_EMAIL` | Superuser email for `createsu` (default: `1000carlos.pena@gmail.com`) |
| `DJANGO_SU_PASSWORD` | Superuser password for `createsu` (required if using the command) |

## Development
```powershell
# Setup
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Database
python manage.py migrate

# Create superuser (password via env or --password)
python manage.py createsu --password=micontraseña

# Run
python manage.py runserver
```

## Conventions
- **Language:** Spanish (es-mx), Mexico City timezone
- **Templates:** Bootstrap 5 with `container-fluid`, responsive tables
- **Forms:** `ModelForm` with explicit `widgets` using Bootstrap classes
- **Messages:** Django contrib messages with Bootstrap alerts (auto-dismiss 5s)
- **Pagination:** `Paginator` with 20 items/page, preserved query params
- **Aggregations:** `annotate()` + `Sum`/`Count` for computed totals (avoid N+1)
- **No REST API** — everything is server-side rendered
- **No tests** currently — add as `pytest` or `unittest` in `inventario/tests/`

## Adding a New Feature
1. If new model: create migration after adding to `models.py`
2. Wire URL in `inventario/urls.py`
3. Create view in `inventario/views.py` (function-based, follow existing patterns)
4. Create template extending `inventario/base.html`
5. Add form class in `inventario/forms.py` if needed (Bootstrap widgets required)

## Deployment (Render)
- `Procfile`: `web: python manage.py migrate && gunicorn imagenologia.wsgi:application --bind 0.0.0.0:$PORT`
- `render.yaml` defines the service + PostgreSQL database
- Build runs `collectstatic --noinput`
- Static files served via WhiteNoise
