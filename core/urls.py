from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import include, path
from django.utils import timezone

# ── Decorador para staff ──────────────────────────────────────────────────────
staff_required = user_passes_test(lambda u: u.is_staff, login_url='/login/')

# ── Flags de países ───────────────────────────────────────────────────────────
_FLAGS = {
    'Peru':'pe','Brasil':'br','Argentina':'ar','Mexico':'mx','Uruguay':'uy',
    'Colombia':'co','Chile':'cl','Ecuador':'ec','Bolivia':'bo','Paraguay':'py',
    'Venezuela':'ve','Alemania':'de','Francia':'fr','Espana':'es',
    'Inglaterra':'gb-eng','Portugal':'pt','Italia':'it','Holanda':'nl',
    'Belgica':'be','Croacia':'hr','Marruecos':'ma','Japon':'jp',
    'Corea':'kr','Australia':'au','USA':'us','Canada':'ca','Senegal':'sn',
}

def _flag_url(nombre):
    code = _FLAGS.get(nombre)
    return f"https://flagcdn.com/48x36/{code}.png" if code else None

# ── Preparar eventos con cuotas procesadas ────────────────────────────────────
_LABEL_MAP = {
    '1':         ('1',             ''),
    'empate':    ('X',             'Empate'),
    '2':         ('2',             ''),
    'over':      ('Más de 2.5',    ''),
    'under':     ('Menos de 2.5',  ''),
    'si':        ('Sí anotan',     ''),
    'no':        ('No ambos',      ''),
    'local':     ('Local −1',      ''),
    'visitante': ('Visitante +1',  ''),
}
_MERCADO_LABELS = {
    '1X2':        '1X2 — Resultado del partido',
    'over_under': 'Over/Under 2.5 goles',
    'btts':       'Ambos equipos anotan',
    'handicap':   'Hándicap',
}

_ORDEN_1X2 = ['1', 'local', 'empate', 'X', 'x', '2', 'visitante']
_ORDEN_OU   = ['over', 'over_2.5', 'under', 'under_2.5']
_ORDEN_BTTS = ['si', 'no']
_ORDEN_HC   = ['local', 'local_-1', 'visitante', 'visitante_+1']

def _ordenar_cuotas(cuotas, tipo):
    ordenes = {
        '1X2':        _ORDEN_1X2,
        'over_under': _ORDEN_OU,
        'btts':       _ORDEN_BTTS,
        'handicap':   _ORDEN_HC,
    }
    orden = ordenes.get(tipo, [])
    def key(c):
        try:    return orden.index(c.seleccion)
        except: return 99
    return sorted(cuotas, key=key)


def _preparar_eventos(qs):
    resultado = []
    for ev in qs:
        mercados = []
        for m in ev.mercados.filter(estado='abierto').order_by('tipo'):
            if m.tipo not in _MERCADO_LABELS:
                continue
            cuotas_raw  = list(m.cuotas.filter(activa=True))
            cuotas_ord  = _ordenar_cuotas(cuotas_raw, m.tipo)
            cuotas_data = []
            for c in cuotas_ord:
                sel = c.seleccion
                # 1X2: acepta tanto las selecciones nuevas ('1','empate','2')
                #       como las antiguas ('local','visitante','X') del fixture
                if m.tipo == '1X2':
                    if sel in ('1', 'local'):
                        lbl, sub = '1', ev.equipo_local[:3].upper()
                    elif sel in ('empate', 'X', 'x', 'draw'):
                        lbl, sub = 'X', 'Empate'
                    elif sel in ('2', 'visitante'):
                        lbl, sub = '2', ev.equipo_visitante[:3].upper()
                    else:
                        lbl, sub = sel, ''
                else:
                    lbl, sub = _LABEL_MAP.get(sel, (sel, ''))
                cuotas_data.append({'cuota': c, 'label': lbl, 'sub': sub})
            if cuotas_data:
                mercados.append({
                    'mercado': m,
                    'label':   _MERCADO_LABELS[m.tipo],
                    'cuotas':  cuotas_data,
                })
        resultado.append({
            'evento':          ev,
            'mercados':        mercados,
            'flag_local':      _flag_url(ev.equipo_local),
            'flag_visitante':  _flag_url(ev.equipo_visitante),
            'local_abbr':      ev.equipo_local[:3].upper(),
            'visitante_abbr':  ev.equipo_visitante[:3].upper(),
        })
    return resultado

# ── Autenticación ─────────────────────────────────────────────────────────────
def login_page(request):
    if request.user.is_authenticated:
        return redirect('panel_admin' if request.user.is_staff else 'inicio')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('panel_admin' if user.is_staff else 'inicio')
        error = 'Usuario o contraseña incorrectos. Verifica tus datos.'

    cuentas_prueba = [
        {'username': 'superadmin',       'rol': 'Super Admin',    'icono': 'crown',         'color': 'var(--primary)'},
        {'username': 'admin_fairbet',    'rol': 'Admin',          'icono': 'shield-halved', 'color': 'var(--primary)'},
        {'username': 'operador_fairbet', 'rol': 'Operador/Staff', 'icono': 'user-tie',      'color': '#3b82f6'},
        {'username': 'jugador_nuevo',    'rol': 'Jugador · S/500','icono': 'user',          'color': 'var(--text-3)'},
        {'username': 'jugador_verificado','rol':'Jugador · S/500','icono': 'user',          'color': 'var(--text-3)'},
    ]
    return render(request, 'login.html', {'error': error, 'cuentas_prueba': cuentas_prueba})


def logout_view(request):
    logout(request)
    return redirect('login')


def registro_page(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    errores = None
    if request.method == 'POST':
        from users.serializers import RegistroUsuarioSerializer
        ser = RegistroUsuarioSerializer(data=request.POST)
        if ser.is_valid():
            user = ser.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('inicio')
        errores = ser.errors

    return render(request, 'registro.html', {'errores': errores})

# ── Páginas de jugador ────────────────────────────────────────────────────────
@login_required
def inicio(request):
    if request.user.is_staff:
        return redirect('panel_admin')

    from betting.models import Evento, EstadoEvento
    from wallet.services import obtener_saldo

    qs = Evento.objects.filter(
        estado__in=[EstadoEvento.PROGRAMADO, EstadoEvento.EN_VIVO]
    ).prefetch_related('mercados__cuotas').order_by('fecha_inicio')[:3]

    return render(request, 'inicio.html', {
        'eventos': _preparar_eventos(qs),
        'saldo':   obtener_saldo(request.user),
    })


@login_required
def eventos_page(request):
    if request.user.is_staff:
        return redirect('panel_admin')

    from betting.models import Evento, EstadoEvento
    from wallet.services import obtener_saldo

    estado = request.GET.get('estado', '')
    qs = Evento.objects.prefetch_related('mercados__cuotas').order_by('fecha_inicio')
    if estado:
        qs = qs.filter(estado=estado)
    else:
        qs = qs.filter(estado__in=[EstadoEvento.PROGRAMADO, EstadoEvento.EN_VIVO])

    return render(request, 'eventos.html', {
        'eventos':       _preparar_eventos(qs),
        'saldo':         obtener_saldo(request.user),
        'estado_filtro': estado,
    })


def evento_detalle_page(request, pk):
    return redirect('eventos')


@login_required
def wallet_page(request):
    if request.user.is_staff:
        return redirect('panel_admin')

    from wallet.models import EntradaContable
    from wallet.services import obtener_saldo
    from users.models import LimiteJuego

    saldo = obtener_saldo(request.user)

    historial = EntradaContable.objects.filter(
        usuario=request.user,
        cuenta='wallet_usuario',
    ).order_by('-creado_en')[:30]

    now = timezone.now()
    mes = EntradaContable.objects.filter(
        usuario=request.user,
        cuenta='wallet_usuario',
        creado_en__year=now.year,
        creado_en__month=now.month,
    )
    total_recargado = mes.filter(tipo_referencia='recarga',       direccion='CREDITO').aggregate(t=Sum('monto'))['t'] or Decimal('0')
    total_apostado  = mes.filter(tipo_referencia='apuesta',       direccion='DEBITO' ).aggregate(t=Sum('monto'))['t'] or Decimal('0')
    total_ganado    = mes.filter(tipo_referencia='pago_ganancia', direccion='CREDITO').aggregate(t=Sum('monto'))['t'] or Decimal('0')

    try:
        limites = LimiteJuego.objects.get(usuario=request.user)
    except LimiteJuego.DoesNotExist:
        limites = None

    return render(request, 'wallet.html', {
        'saldo':           saldo,
        'historial':       historial,
        'total_recargado': total_recargado,
        'total_apostado':  total_apostado,
        'total_ganado':    total_ganado,
        'balance_neto':    total_ganado - total_apostado,
        'limites':         limites,
    })


@login_required
def mis_apuestas_page(request):
    if request.user.is_staff:
        return redirect('panel_admin')

    from betting.models import Apuesta

    estado_filtro = request.GET.get('estado', '')
    qs = Apuesta.objects.filter(usuario=request.user).select_related(
        'cuota__mercado__evento'
    ).order_by('-creado_en')

    if estado_filtro:
        qs = qs.filter(estado=estado_filtro)

    todas = Apuesta.objects.filter(usuario=request.user)
    stats = {
        'total':      todas.count(),
        'ganadas':    todas.filter(estado='ganada').count(),
        'perdidas':   todas.filter(estado='perdida').count(),
        'pendientes': todas.filter(estado='aceptada').count(),
    }

    return render(request, 'mis_apuestas.html', {
        'apuestas':      qs,
        'stats':         stats,
        'estado_filtro': estado_filtro,
    })

# ── Panel admin ───────────────────────────────────────────────────────────────
@staff_required
def panel_admin_page(request):
    from betting.models import Apuesta, Evento, EstadoEvento
    from users.models import Usuario

    total_usuarios  = Usuario.objects.count()
    total_apuestas  = Apuesta.objects.count()
    volumen         = Apuesta.objects.aggregate(v=Sum('monto_apostado'))['v'] or Decimal('0')
    eventos_activos = Evento.objects.filter(
        estado__in=[EstadoEvento.PROGRAMADO, EstadoEvento.EN_VIVO]
    ).count()

    try:
        from audit.models import ActividadSospechosa
        alertas = ActividadSospechosa.objects.filter(revisado=False).order_by('-id')[:20]
    except Exception:
        alertas = []

    return render(request, 'panel_admin.html', {
        'total_usuarios':  total_usuarios,
        'total_apuestas':  total_apuestas,
        'volumen':         volumen,
        'eventos_activos': eventos_activos,
        'eventos':         Evento.objects.prefetch_related('mercados').order_by('-id'),
        'usuarios':        Usuario.objects.all().order_by('-date_joined'),
        'alertas':         alertas,
    })


# ── URL patterns ──────────────────────────────────────────────────────────────
urlpatterns = [
    path("",                inicio,             name="inicio"),
    path("login/",          login_page,         name="login"),
    path("logout/",         logout_view,        name="logout"),
    path("registro/",       registro_page,      name="registro"),
    path("eventos/",        eventos_page,       name="eventos"),
    path("eventos/<int:pk>/", evento_detalle_page, name="evento_detalle"),
    path("wallet/",         wallet_page,        name="wallet"),
    path("mis-apuestas/",   mis_apuestas_page,  name="mis_apuestas"),
    path("panel-admin/",    panel_admin_page,   name="panel_admin"),

    path("admin/",          admin.site.urls),

    path("api/usuarios/",   include("users.urls")),
    path("api/wallet/",     include("wallet.urls")),
    path("api/",            include("betting.urls")),
    path("api/admin/",      include("audit.urls")),
]