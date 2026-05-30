# FairBet Lab 🎲

Plataforma educativa de apuestas deportivas con moneda virtual.  
Desarrollada con **Django 5**, **PostgreSQL**, **Redis** y **Docker**.

> ⚠️ **Plataforma educativa** — Usa moneda virtual sin valor real. No constituye una casa de apuestas.

---

## 📋 Requisitos previos

Instala estas herramientas antes de continuar:

| Herramienta | Descarga |
|---|---|
| **Git** | https://git-scm.com/downloads |
| **Docker Desktop** | https://www.docker.com/products/docker-desktop |

Verifica que están instalados:
```bash
git --version
docker --version
docker compose version
```

---

## 🚀 Pasos para ejecutar el proyecto

### 1. Clonar el repositorio

```bash
git clone https://github.com/Jerson6463/Sistema_Apuestas.git
cd Sistema_Apuestas
```

### 2. Levantar los contenedores

```bash
docker compose up --build
```

> La primera vez tarda unos minutos porque descarga las imágenes de Docker.  
> Espera hasta ver este mensaje en la consola:
> ```
> web-1  | Listening on TCP address 0.0.0.0:8000
> ```

### 3. Crear usuarios de prueba

Abre **otra terminal** (sin cerrar la anterior) y ejecuta:

```bash
docker compose exec web python manage.py seed_usuarios
```

Deberías ver:
```
✓  Usuario 'superadmin' creado
✓  Usuario 'admin_fairbet' creado
✓  Usuario 'operador_fairbet' creado
...
Contraseña para todos: FairBet2026!
```

### 4. Abrir en el navegador

```
http://localhost:8000
```

---

## 👥 Usuarios de prueba

| Usuario | Contraseña | Rol | Acceso |
|---|---|---|---|
| `superadmin` | `FairBet2026!` | Super Admin | Panel Admin + Django Admin (`/admin/`) |
| `admin_fairbet` | `FairBet2026!` | Admin | Panel Admin + Django Admin |
| `operador_fairbet` | `FairBet2026!` | Operador / Staff | Solo Panel Admin |
| `jugador_nuevo` | `FairBet2026!` | Jugador | Apuestas + Wallet (S/ 500) |
| `jugador_verificado` | `FairBet2026!` | Jugador | Apuestas + Wallet (S/ 500) |
| `jugador_pendiente` | `FairBet2026!` | Jugador | Sin fichas, pendiente KYC |

---

## 🗂️ Módulos del sistema

### Para jugadores
| Módulo | URL | Descripción |
|---|---|---|
| Inicio | `/` | Eventos destacados y betslip |
| Futbol / Eventos | `/eventos/` | Lista de partidos con cuotas |
| En Vivo | `/eventos/?estado=en_vivo` | Partidos en curso |
| Mis Apuestas | `/mis-apuestas/` | Historial de apuestas y cash-out |
| Wallet | `/wallet/` | Saldo, recargas, retiros y límites |

### Para administradores / staff
| Módulo | URL | Descripción |
|---|---|---|
| Panel Admin | `/panel-admin/` | Dashboard, eventos, usuarios, fraude |
| Django Admin | `/admin/` | Administración completa (solo superadmin) |

---

## 🛠️ Comandos útiles

```bash
# Ver logs del servidor en tiempo real
docker compose logs -f web

# Detener todos los contenedores
docker compose down

# Detener y eliminar volúmenes (resetea la base de datos)
docker compose down -v

# Volver a levantar sin reconstruir
docker compose up

# Acceder a la consola de Django
docker compose exec web python manage.py shell

# Crear un superusuario manualmente
docker compose exec web python manage.py createsuperuser
```

---

## 🏗️ Arquitectura

```
Sistema_Apuestas/
├── core/           # Configuración Django y vistas principales
├── users/          # Gestión de usuarios, KYC, límites
├── betting/        # Eventos, mercados, cuotas y apuestas
├── wallet/         # Wallet con contabilidad de doble entrada
├── audit/          # Auditoría inmutable y detección de fraude
├── templates/      # HTML con Django template engine
└── static/         # CSS y JavaScript
```

**Stack tecnológico:**
- **Backend:** Django 5 + Django REST Framework
- **Base de datos:** PostgreSQL 15
- **Caché / Cola:** Redis 7
- **Tareas async:** Celery + Celery Beat
- **WebSockets:** Django Channels + Daphne
- **Contenedores:** Docker + Docker Compose

---

## ⚙️ Variables de entorno

El proyecto funciona sin configuración adicional en desarrollo.  
Las variables se encuentran en `docker-compose.yml`.

| Variable | Valor por defecto |
|---|---|
| `DEBUG` | `True` |
| `DATABASE_URL` | PostgreSQL local en Docker |
| `REDIS_URL` | Redis local en Docker |

---

## ❓ Solución de problemas

**El puerto 8000 ya está en uso:**
```bash
# Cambiar el puerto en docker-compose.yml
ports:
  - "8001:8000"   # Cambia 8000 por otro puerto
```

**Error de base de datos al iniciar:**
```bash
docker compose down -v
docker compose up --build
```

**Los usuarios no existen:**
```bash
docker compose exec web python manage.py seed_usuarios
```

**Página en blanco o CSS roto:**  
Presiona `Ctrl + Shift + R` en el navegador para limpiar el caché.

---

## 👨‍💻 Desarrollado por

**KellyCubas** — Taller de Lenguajes de Programación, 9vo Ciclo  
Universidad — 2026
