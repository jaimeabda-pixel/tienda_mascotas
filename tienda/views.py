from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal, InvalidOperation
from io import BytesIO
import json
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import TruncMonth
from django.contrib.auth import get_user_model
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm

from .models import Producto, Cliente, Venta, VentaItem, Vendedor
from .forms import ProductoForm, ClienteForm, VentaForm, VendedorForm, VendedorRegistroForm
from django.template.loader import render_to_string
from datetime import datetime

# ---------------------------
# VISTA PRINCIPAL / DASHBOARD
# ---------------------------
@login_required
def inicio(request):
    today = timezone.now().date()
    
    if request.user.is_superuser:
        # --- DASHBOARD ADMIN ---
        productos = Producto.objects.all()
        clientes_total = Cliente.objects.count()
        ventas_hoy = VentaItem.objects.filter(venta__fecha__date=today).count()
        productos_stock_bajo = Producto.objects.filter(stock__lte=5)
        
        # Top producto
        top_producto = (
            Producto.objects
            .annotate(total_vendido=Sum('ventaitem__cantidad'))
            .order_by('-total_vendido')
            .first()
        )
        total_vendido_top = top_producto.total_vendido if top_producto else 0
        
        # Nuevas métricas Admin
        ingresos_hoy = sum(v.total() for v in Venta.objects.filter(fecha__date=today))
        
        vendedores_activos = Vendedor.objects.filter(is_active=True).count()
        comision_total_pagada = Venta.objects.aggregate(Sum('comision_monto'))['comision_monto__sum'] or 0

        context = {
            'role': 'admin',
            'productos': productos,
            'clientes_total': clientes_total,
            'ventas_hoy': ventas_hoy,
            'ingresos_hoy': ingresos_hoy,
            'productos_stock_bajo': productos_stock_bajo,
            'top_producto': top_producto,
            'total_vendido_top': total_vendido_top,
            'vendedores_activos': vendedores_activos,
            'comision_total_pagada': comision_total_pagada,
        }
    else:
        # --- DASHBOARD VENDEDOR ---
        usuario = request.user
        
        # Ventas de hoy del vendedor
        ventas_hoy_qs = Venta.objects.filter(vendedor=usuario, fecha__date=today)
        ventas_hoy_count = ventas_hoy_qs.count()
        total_vendido_hoy = sum(v.total() for v in ventas_hoy_qs)
        
        # Comisión del mes
        inicio_mes = today.replace(day=1)
        comision_mes = Venta.objects.filter(vendedor=usuario, fecha__date__gte=inicio_mes).aggregate(Sum('comision_monto'))['comision_monto__sum'] or 0
        
        # Meta personal
        meta = usuario.meta_mensual
        # Calculamos progreso como entero para evitar uso de filtros complejos en template
        progreso_meta = int((comision_mes / meta * 100)) if meta > 0 else 0
        
        # Últimas ventas
        ultimas_ventas = Venta.objects.filter(vendedor=usuario).order_by('-fecha')[:5]

        context = {
            'role': 'vendedor',
            'ventas_hoy_count': ventas_hoy_count,
            'total_vendido_hoy': total_vendido_hoy,
            'comision_mes': comision_mes,
            'meta': meta,
            'progreso_meta': min(progreso_meta, 100),
            'ultimas_ventas': ultimas_ventas,
        }

    return render(request, 'tienda/index.html', context)


# ---------------------------
# CRUD PRODUCTOS
# ---------------------------
@login_required
def productos_list(request):
    query = request.GET.get('q', '')
    productos = Producto.objects.filter(nombre__icontains=query) if query else Producto.objects.all()

    # Stats for Dashboard
    total_productos = Producto.objects.count()
    low_stock_count = Producto.objects.filter(stock__lte=5).count()
    total_valor_inventario = sum(p.precio * p.stock for p in Producto.objects.all())

    context = {
        'productos': productos,
        'query': query,
        'total_productos': total_productos,
        'low_stock_count': low_stock_count,
        'total_valor_inventario': total_valor_inventario,
    }
    return render(request, 'tienda/productos_list.html', context)

@login_required
def productos_create(request):
    if not request.user.is_superuser:
        messages.error(request, "No tienes permisos para crear productos.")
        return redirect('inicio')
        
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('productos_list')
    else:
        form = ProductoForm()
    return render(request, 'tienda/productos_form.html', {'form': form, 'accion': 'Registrar Producto'})

@login_required
def productos_update(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "No tienes permisos para editar productos.")
        return redirect('inicio')

    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            return redirect('productos_list')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'tienda/productos_form.html', {'form': form, 'accion': 'Editar Producto'})

@login_required
def productos_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "No tienes permisos para eliminar productos.")
        return redirect('inicio')

    producto = get_object_or_404(Producto, pk=pk)
    producto.delete()
    return redirect('productos_list')


# ---------------------------
# CRUD CLIENTES
# ---------------------------
@login_required
def clientes_list(request):
    # Vendedores ven sus clientes, Admin ve todos (o todos ven todos, según requerimiento "Lista de sus clientes")
    # Asumiremos: Admin ve todos, Vendedor ve los que ha registrado o todos?
    # El requerimiento dice "Lista de sus clientes". Vamos a filtrar.
    if request.user.is_superuser:
        clientes = Cliente.objects.all()
    else:
        clientes = Cliente.objects.filter(vendedor=request.user)
        
    return render(request, 'tienda/clientes_list.html', {'clientes': clientes})

@login_required
def clientes_create(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.vendedor = request.user # Asignar vendedor creador
            cliente.save()
            return redirect('clientes_list')
    else:
        form = ClienteForm()
    return render(request, 'tienda/clientes_form.html', {'form': form, 'accion': 'Registrar Cliente'})

@login_required
def clientes_update(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    # Verificar permisos
    if not request.user.is_superuser and cliente.vendedor != request.user:
        messages.error(request, "No puedes editar este cliente.")
        return redirect('clientes_list')

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('clientes_list')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'tienda/clientes_form.html', {'form': form, 'accion': 'Editar Cliente'})

@login_required
def clientes_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if not request.user.is_superuser and cliente.vendedor != request.user:
        messages.error(request, "No puedes eliminar este cliente.")
        return redirect('clientes_list')
        
    if request.method == 'POST':
        cliente.delete()
        return redirect('clientes_list')
    return render(request, 'tienda/clientes_confirm_delete.html', {'cliente': cliente})


# ---------------------------
# CRUD VENTAS
# ---------------------------
@login_required
def ventas_list(request):
    # Filtrar ventas según rol
    if request.user.is_superuser:
        ventas = Venta.objects.prefetch_related('items__producto').select_related('cliente', 'vendedor').order_by('-fecha')
    else:
        ventas = Venta.objects.filter(vendedor=request.user).prefetch_related('items__producto').select_related('cliente', 'vendedor').order_by('-fecha')
    
    # Cálculos para el dashboard de ventas (basado en el queryset filtrado)
    total_ventas_count = ventas.count()
    total_ingresos = sum(v.total() for v in ventas)
    
    today = timezone.now().date()
    ventas_hoy_count = ventas.filter(fecha__date=today).count()
    ingresos_hoy = sum(v.total() for v in ventas if v.fecha.date() == today)

    context = {
        'ventas': ventas,
        'total_ventas_count': total_ventas_count,
        'total_ingresos': total_ingresos,
        'ventas_hoy_count': ventas_hoy_count,
        'ingresos_hoy': ingresos_hoy,
    }
    return render(request, 'tienda/ventas_list.html', context)


@login_required
def ventas_create(request, producto_id=None):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        carrito_data = request.POST.get('carrito_data')
        metodo_pago = request.POST.get('metodo_pago', 'Efectivo')
        efectivo_recibido = request.POST.get('efectivo_recibido', '0')
        notas = request.POST.get('notas', '')

        if not carrito_data:
            messages.error(request, 'Debes agregar al menos un producto al carrito antes de registrar la venta.')
            return redirect('ventas_create')

        try:
            # Permitir ventas sin cliente específico (Cliente General)
            cliente = None
            if cliente_id and cliente_id != 'general':
                try:
                    cliente = Cliente.objects.get(id=cliente_id)
                except Cliente.DoesNotExist:
                    cliente = None
            
            carrito = json.loads(carrito_data)

            # Calculamos total de la venta como Decimal
            total_venta = Decimal('0.00')
            for item in carrito:
                producto = get_object_or_404(Producto, id=item['id'])
                cantidad = int(item['cantidad'])
                subtotal = Decimal(producto.precio) * cantidad
                total_venta += subtotal

            # Validación efectivo
            if metodo_pago == 'Efectivo':
                try:
                    efectivo_recibido = Decimal(efectivo_recibido)
                except InvalidOperation:
                    messages.error(request, 'Debes ingresar un monto válido de efectivo recibido.')
                    return redirect('ventas_create')

                if efectivo_recibido < total_venta:
                    messages.error(request, f'El efectivo recibido (${efectivo_recibido:.2f}) es menor al total (${total_venta:.2f}).')
                    return redirect('ventas_create')
            else:
                efectivo_recibido = None  # Para métodos distintos a efectivo

            # Crear la venta
            vuelto = (efectivo_recibido - total_venta) if efectivo_recibido is not None else Decimal('0.00')
            venta = Venta.objects.create(
                cliente=cliente,
                vendedor=request.user,
                metodo_pago=metodo_pago,
                efectivo_recibido=efectivo_recibido,
                vuelto=vuelto,
                notas=notas,
                estado='Pagada' # Por defecto pagada en POS
            )

            # Crear los items de la venta y actualizar stock
            for item in carrito:
                producto = get_object_or_404(Producto, id=item['id'])
                cantidad = int(item['cantidad'])

                VentaItem.objects.create(
                    venta=venta,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=producto.precio
                )

                producto.stock -= cantidad
                producto.save()

            messages.success(request, 'Venta registrada correctamente.')
            return redirect('ventas_list')

        except Exception as e:
            messages.error(request, f'Error al registrar la venta: {e}')
            return redirect('ventas_create')

    # GET
    # Filtrar clientes si es vendedor
    if request.user.is_superuser:
        clientes = Cliente.objects.all()
    else:
        clientes = Cliente.objects.filter(vendedor=request.user)
        
    productos = Producto.objects.all() # Productos los ven todos
    producto_preseleccionado = None
    if producto_id:
        producto_preseleccionado = get_object_or_404(Producto, pk=producto_id)

    return render(
        request,
        'tienda/ventas_form.html',
        {
            'clientes': clientes,
            'productos': productos,
            'producto_preseleccionado': producto_preseleccionado,
            "user": request.user
        }
    )
    
@login_required
def ventas_delete(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    
    # Solo admin puede eliminar ventas, o vendedor sus propias ventas (si se permite)
    # Requerimiento: Admin puede eliminar. Vendedor NO dice explícitamente, pero "NO puede crear ni editar cuentas...". 
    # Asumiremos que Vendedor NO puede eliminar ventas para seguridad, solo Admin.
    if not request.user.is_superuser:
        messages.error(request, "No tienes permisos para eliminar ventas.")
        return redirect('ventas_list')

    for item in venta.items.all():
        item.producto.stock += item.cantidad
        item.producto.save()
    venta.delete()
    messages.success(request, "La venta se eliminó correctamente y el stock fue restaurado.")
    return redirect('ventas_list')


# ---------------------------
# PDF FACTURA (ReportLab)
# ---------------------------
@login_required
def ventas_factura_pdf_rl(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    # Verificar acceso
    if not request.user.is_superuser and venta.vendedor != request.user:
        return HttpResponse("No tienes permiso para ver esta factura.", status=403)
        
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elementos = []

    # Encabezado
    elementos.append(Paragraph("<b>TIENDA PARA MASCOTAS</b>", styles["Title"]))
    elementos.append(Spacer(1, 12))
    elementos.append(Paragraph(f"<b>Factura N°:</b> {venta.factura_num}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Fecha:</b> {venta.fecha.strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    elementos.append(Spacer(1, 12))

    # Cliente
    if venta.cliente:
        elementos.append(Paragraph("<b>Datos del Cliente</b>", styles["Heading2"]))
        elementos.append(Paragraph(f"<b>Nombre:</b> {venta.cliente.nombre}", styles["Normal"]))
        elementos.append(Paragraph(f"<b>Correo:</b> {venta.cliente.correo}", styles["Normal"]))
    else:
        elementos.append(Paragraph("<b>Cliente General</b>", styles["Heading2"]))
        
    elementos.append(Spacer(1, 12))

    # Tabla de productos
    data = [["Producto", "Cantidad", "Precio Unitario", "Subtotal"]]
    for item in venta.items.all():
        data.append([item.producto.nombre, str(item.cantidad), f"${item.precio_unitario:.2f}", f"${item.subtotal():.2f}"])
    table = Table(data, colWidths=[80*mm, 30*mm, 40*mm, 40*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
    ]))
    elementos.append(table)
    elementos.append(Spacer(1, 12))

    # Total
    elementos.append(Paragraph(f"<b>Método de pago:</b> {venta.metodo_pago}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Total a pagar:</b> ${venta.total():.2f}", styles["Heading2"]))
    if venta.metodo_pago == "Efectivo" and venta.efectivo_recibido:
        elementos.append(Paragraph(f"<b>Efectivo recibido:</b> ${venta.efectivo_recibido:.2f}", styles["Normal"]))
        elementos.append(Paragraph(f"<b>Vuelto:</b> ${venta.vuelto:.2f}", styles["Normal"]))

    elementos.append(Spacer(1, 20))
    elementos.append(Paragraph("¡Gracias por su compra!", styles["Normal"]))

    doc.build(elementos)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Factura_{venta.factura_num}.pdf"'
    response.write(pdf)
    return response


# ---------------------------
# Páginas Estáticas
# ---------------------------
def contacto(request):
    mensaje = ''
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        texto = request.POST.get('mensaje')
        mensaje = 'Gracias por contactarnos, tu mensaje ha sido enviado.'
    return render(request, 'tienda/contacto.html', {'mensaje': mensaje})

def acerca(request):
    return render(request, 'tienda/acerca.html')


# ---------------------------
# Historial y detalle de ventas
# ---------------------------
User = get_user_model()

@login_required
def ventas_historial(request):
    # Obtener filtros desde el GET
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    vendedor_id = request.GET.get('vendedor')

    # Base de datos inicial
    if request.user.is_superuser:
        ventas = Venta.objects.all().order_by('-fecha')
    else:
        ventas = Venta.objects.filter(vendedor=request.user).order_by('-fecha')

    # Filtrar por fecha inicial
    if fecha_inicio:
        ventas = ventas.filter(fecha__date__gte=fecha_inicio)

    # Filtrar por fecha final
    if fecha_fin:
        ventas = ventas.filter(fecha__date__lte=fecha_fin)

    # Filtrar por vendedor (Solo Admin puede filtrar por otros vendedores)
    if request.user.is_superuser and vendedor_id:
        ventas = ventas.filter(vendedor_id=vendedor_id)

    # Total ventas
    total_ventas = sum(v.total() for v in ventas)

    # Pasamos todos los vendedores al template solo si es admin
    vendedores = User.objects.all() if request.user.is_superuser else []

    return render(request, 'tienda/ventas_historial.html', {
        'ventas': ventas,
        'vendedores': vendedores,
        'total_ventas': total_ventas,

        # ❗ Datos para mantener filtros en pantalla
        'f_fecha_inicio': fecha_inicio,
        'f_fecha_fin': fecha_fin,
        'f_vendedor': vendedor_id,
    })

@login_required
def ventas_detalle(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    # Verificar permiso
    if not request.user.is_superuser and venta.vendedor != request.user:
        messages.error(request, "No tienes permiso para ver esta venta.")
        return redirect('ventas_list')
        
    items = venta.items.all()
    return render(request, 'tienda/ventas_detalle.html', {'venta': venta})


# ---------------------------
# CRUD VENDEDORES
# ---------------------------
@login_required
def vendedores_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado.")
        return redirect('inicio')
        
    vendedores = Vendedor.objects.all()
    return render(request, 'tienda/vendedores_list.html', {'vendedores': vendedores})

@login_required
def vendedores_create(request):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado.")
        return redirect('inicio')

    if request.method == 'POST':
        form = VendedorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('vendedores_list')
    else:
        form = VendedorForm()
    return render(request, 'tienda/vendedores_form.html', {'form': form})
    
@login_required
def vendedores_update(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado.")
        return redirect('inicio')
        
    vendedor = get_object_or_404(Vendedor, pk=pk)
    if request.method == 'POST':
        form = VendedorForm(request.POST, instance=vendedor)
        if form.is_valid():
            form.save()
            return redirect('vendedores_list')
    else:
        form = VendedorForm(instance=vendedor)
    return render(request, 'tienda/vendedores_form.html', {'form': form})

@login_required
def vendedores_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado.")
        return redirect('inicio')
        
    vendedor = get_object_or_404(Vendedor, pk=pk)
    vendedor.delete()
    return redirect('vendedores_list')

def registrar_vendedor(request):
    if request.method == 'POST':
        form = VendedorRegistroForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vendedor registrado correctamente')
            return redirect('login')
    else:
        form = VendedorRegistroForm()
    return render(request, 'tienda/registrar_vendedor.html', {'form': form})


# ---------------------------
# LOGIN / LOGOUT
# ---------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next') or 'inicio'
            return redirect(next_url)
        else:
            messages.error(request, "Usuario o contraseña incorrecta")
            
    vendedores = Vendedor.objects.filter(is_active=True)
    return render(request, 'tienda/login.html', {'vendedores': vendedores})

def logout_view(request):
    logout(request)
    return redirect('login')


# ---------------------------
# AJAX: agregar cliente desde venta
# ---------------------------
@csrf_exempt
def cliente_add_ajax(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        correo = request.POST.get('correo', '')
        telefono = request.POST.get('telefono', '')

        if not nombre:
            return JsonResponse({'error': 'El nombre es obligatorio'}, status=400)

        cliente = Cliente.objects.create(nombre=nombre, correo=correo, telefono=telefono, vendedor=request.user)
        return JsonResponse({'id': cliente.id, 'nombre': cliente.nombre})

    return JsonResponse({'error': 'Método no permitido'}, status=405)


# ---------------------------
# POS
# ---------------------------
@login_required
def ventas_pos(request):
    productos = Producto.objects.filter(stock__gt=0)
    return render(request, 'tienda/ventas_pos.html', {'productos': productos})

@csrf_exempt
def ventas_pos_register(request):
    if request.method == "POST":
        try:
            data = json.loads(request.POST.get('carrito', '[]'))
            if not data:
                return JsonResponse({'error': 'El carrito está vacío'}, status=400)

            total = 0
            venta = Venta.objects.create(cliente=None, vendedor=request.user, metodo_pago="Efectivo")

            for item in data:
                prod_id = item.get('id')
                if not prod_id:
                    return JsonResponse({'error': 'Falta el ID del producto'}, status=400)

                try:
                    prod = Producto.objects.get(pk=prod_id)
                except Producto.DoesNotExist:
                    venta.delete()
                    return JsonResponse({'error': f'El producto con ID {prod_id} no existe'}, status=404)

                cantidad = int(item.get('cantidad', 1))
                if cantidad > prod.stock:
                    venta.delete()
                    return JsonResponse({'error': f'Stock insuficiente para {prod.nombre}'}, status=400)

                subtotal = prod.precio * cantidad
                total += subtotal

                VentaItem.objects.create(venta=venta, producto=prod, cantidad=cantidad, precio_unitario=prod.precio)
                prod.stock -= cantidad
                prod.save()

            venta.total = total
            venta.save()
            return JsonResponse({'ok': True, 'mensaje': 'Venta registrada correctamente'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)
@csrf_exempt
def ventas_pos_producto_codigo(request):
    if request.method == 'POST':
        codigo = request.POST.get('codigo')
        try:
            producto = Producto.objects.get(codigo_barras=codigo)
            return JsonResponse({
                'ok': True,
                'producto': {
                    'id': producto.id,
                    'nombre': producto.nombre,
                    'precio': float(producto.precio)
                }
            })
        except Producto.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Producto no encontrado'})
    return JsonResponse({'ok': False, 'error': 'Método no permitido'})




@login_required
def buscar_productos_htmx(request):
    query = request.GET.get('buscar', '')  # ❗ debe ser 'buscar', igual que en el input
    if query:
        productos = Producto.objects.filter(Q(nombre__icontains=query) | Q(codigo_barras__icontains=query))
    else:
        productos = Producto.objects.all()
    return render(request, 'tienda/partials/productos_cards.html', {'productos': productos})

@login_required
def graficos(request):
    if not request.user.is_superuser:
         messages.error(request, "Acceso denegado a reportes globales.")
         return redirect('inicio')

    from django.db.models import F
    
    # --- DATOS DE VENTAS ---
    # 1. Ventas por Método de Pago
    metodos_pago = Venta.objects.values('metodo_pago').annotate(cantidad=Count('id'), total=Sum(F('items__cantidad') * F('items__precio_unitario')))
    
    # 2. Top 5 Productos Más Vendidos
    top_productos = (
        VentaItem.objects
        .values('producto__nombre')
        .annotate(total_vendido=Sum('cantidad'))
        .order_by('-total_vendido')[:5]
    )
    
    # 3. Ventas por Mes
    ventas_mes = (
        Venta.objects
        .annotate(mes=TruncMonth('fecha'))
        .values('mes')
        .annotate(total=Sum(F('items__cantidad') * F('items__precio_unitario')))
        .order_by('mes')
    )

    # --- DATOS DE INVENTARIO (NUEVO) ---
    total_inventario_valor = sum(p.precio * p.stock for p in Producto.objects.all())
    total_productos_count = Producto.objects.count()
    productos_bajo_stock_count = Producto.objects.filter(stock__lte=5).count()
    
    # Top 5 Productos con mayor valor en inventario
    top_valor_inventario = sorted(
        Producto.objects.all(), 
        key=lambda p: p.precio * p.stock, 
        reverse=True
    )[:5]

    # Preparar datos para Chart.js
    labels_mes = [v['mes'].strftime('%B %Y') for v in ventas_mes] if ventas_mes else []
    data_mes = [float(v['total']) for v in ventas_mes] if ventas_mes else []

    labels_prod = [p['producto__nombre'] for p in top_productos]
    data_prod = [p['total_vendido'] for p in top_productos]

    labels_pago = [m['metodo_pago'] for m in metodos_pago]
    data_pago = [float(m['total']) if m['total'] else 0 for m in metodos_pago]
    
    # Datos para gráfico de valor de inventario
    labels_inv = [p.nombre for p in top_valor_inventario]
    data_inv = [float(p.precio * p.stock) for p in top_valor_inventario]

    context = {
        # Ventas
        'labels_mes': json.dumps(labels_mes),
        'data_mes': json.dumps(data_mes),
        'labels_prod': json.dumps(labels_prod),
        'data_prod': json.dumps(data_prod),
        'labels_pago': json.dumps(labels_pago),
        'data_pago': json.dumps(data_pago),
        
        # Inventario
        'total_inventario_valor': total_inventario_valor,
        'total_productos_count': total_productos_count,
        'productos_bajo_stock_count': productos_bajo_stock_count,
        'labels_inv': json.dumps(labels_inv),
        'data_inv': json.dumps(data_inv),
        
        'has_data': bool(ventas_mes or top_productos or metodos_pago or total_productos_count),
    }

    return render(request, 'tienda/graficos.html', context)

@login_required
def perfil(request):
    from datetime import datetime
    from django.db.models import F
    
    usuario = request.user
    
    # Estadísticas de ventas del usuario
    ventas_usuario = Venta.objects.filter(vendedor=usuario)
    total_ventas = ventas_usuario.count()
    
    # Ventas del mes actual
    hoy = datetime.now()
    inicio_mes = hoy.replace(day=1)
    ventas_mes = ventas_usuario.filter(fecha__gte=inicio_mes).count()
    
    # Total vendido (suma de todos los items)
    total_vendido = VentaItem.objects.filter(venta__vendedor=usuario).aggregate(
        total=Sum(F('cantidad') * F('precio_unitario'))
    )['total'] or 0
    
    # Últimas 5 ventas
    ultimas_ventas = ventas_usuario.order_by('-fecha')[:5]
    
    # Manejo del formulario de actualización de perfil
    if request.method == 'POST':
        usuario.first_name = request.POST.get('first_name', '')
        usuario.last_name = request.POST.get('last_name', '')
        usuario.email = request.POST.get('email', '')
        usuario.telefono = request.POST.get('telefono', '')
        usuario.direccion = request.POST.get('direccion', '')
        
        # Manejo de la foto de perfil
        if 'foto_perfil' in request.FILES:
            usuario.foto_perfil = request.FILES['foto_perfil']
        
        usuario.save()
        messages.success(request, 'Perfil actualizado correctamente')
        return redirect('perfil')
    
    context = {
        'usuario': usuario,
        'total_ventas': total_ventas,
        'ventas_mes': ventas_mes,
        'total_vendido': total_vendido,
        'ultimas_ventas': ultimas_ventas,
    }
    return render(request, 'tienda/perfil.html', context)

@login_required
def configuracion(request):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado.")
        return redirect('inicio')
    return render(request, 'tienda/configuracion.html')

@login_required
def notificaciones(request):
    return render(request, 'tienda/notificaciones.html')
