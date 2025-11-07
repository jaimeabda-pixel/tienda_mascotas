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
from django.db.models import Sum

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm

from .models import Producto, Cliente, Venta, VentaItem, Vendedor
from .forms import ProductoForm, ClienteForm, VentaForm, VendedorForm, VendedorRegistroForm

# ---------------------------
# VISTA PRINCIPAL / DASHBOARD
# ---------------------------
@login_required
def inicio(request):
    productos = Producto.objects.all()
    clientes_total = Cliente.objects.count()
    today = timezone.now().date()
    ventas_hoy = VentaItem.objects.filter(venta__fecha__date=today).count()
    productos_stock_bajo = Producto.objects.filter(stock__lte=5)
    top_producto = (
        Producto.objects
        .annotate(total_vendido=Sum('ventaitem__cantidad'))
        .order_by('-total_vendido')
        .first()
    )
    total_vendido_top = top_producto.total_vendido if top_producto else 0

    context = {
        'productos': productos,
        'clientes_total': clientes_total,
        'ventas_hoy': ventas_hoy,
        'productos_stock_bajo': productos_stock_bajo,
        'top_producto': top_producto,
        'total_vendido_top': total_vendido_top,
    }

    return render(request, 'tienda/index.html', context)


# ---------------------------
# CRUD PRODUCTOS
# ---------------------------
@login_required
def productos_list(request):
    query = request.GET.get('q', '')
    productos = Producto.objects.filter(nombre__icontains=query) if query else Producto.objects.all()
    return render(request, 'tienda/productos_list.html', {'productos': productos, 'query': query})

@login_required
def productos_create(request):
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
    producto = get_object_or_404(Producto, pk=pk)
    producto.delete()
    return redirect('productos_list')


# ---------------------------
# CRUD CLIENTES
# ---------------------------
@login_required
def clientes_list(request):
    clientes = Cliente.objects.all()
    return render(request, 'tienda/clientes_list.html', {'clientes': clientes})

@login_required
def clientes_create(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('clientes_list')
    else:
        form = ClienteForm()
    return render(request, 'tienda/clientes_form.html', {'form': form, 'accion': 'Registrar Cliente'})

@login_required
def clientes_update(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
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
    if request.method == 'POST':
        cliente.delete()
        return redirect('clientes_list')
    return render(request, 'tienda/clientes_confirm_delete.html', {'cliente': cliente})


# ---------------------------
# CRUD VENTAS
# ---------------------------
@login_required
def ventas_list(request):
    # Prefetch items y productos para no hacer consultas adicionales por cada venta
    ventas = Venta.objects.prefetch_related('items__producto').select_related('cliente', 'vendedor').all()
    return render(request, 'tienda/ventas_list.html', {'ventas': ventas})



from decimal import Decimal, InvalidOperation

@login_required
def ventas_create(request, producto_id=None):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        carrito_data = request.POST.get('carrito_data')
        metodo_pago = request.POST.get('metodo_pago', 'Efectivo')
        efectivo_recibido = request.POST.get('efectivo_recibido', '0')

        if not cliente_id:
            messages.error(request, 'Debes seleccionar un cliente antes de registrar la venta.')
            return redirect('ventas_create')

        if not carrito_data:
            messages.error(request, 'Debes agregar al menos un producto al carrito antes de registrar la venta.')
            return redirect('ventas_create')

        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
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
                vuelto=vuelto
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
    clientes = Cliente.objects.all()
    productos = Producto.objects.all()
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
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elementos = []

    # Encabezado
    elementos.append(Paragraph("<b>TIENDA DE MASCOTAS</b>", styles["Title"]))
    elementos.append(Spacer(1, 12))
    elementos.append(Paragraph(f"<b>Factura N°:</b> {venta.factura_num}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Fecha:</b> {venta.fecha.strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    elementos.append(Spacer(1, 12))

    # Cliente
    elementos.append(Paragraph("<b>Datos del Cliente</b>", styles["Heading2"]))
    elementos.append(Paragraph(f"<b>Nombre:</b> {venta.cliente.nombre}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Correo:</b> {venta.cliente.correo}", styles["Normal"]))
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
    if venta.metodo_pago == "Efectivo":
        elementos.append(Paragraph(f"<b>Efectivo recibido:</b> ${venta.efectivo_recibido:.2f}", styles["Normal"]))
        elementos.append(Paragraph(f"<b>Vuelto:</b> ${venta.vuelto:.2f}", styles["Normal"]))

    elementos.append(Spacer(1, 20))
    elementos.append(Paragraph("Gracias por su compra 💙", styles["Normal"]))

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
@login_required
def ventas_historial(request):
    ventas = Venta.objects.select_related('cliente').prefetch_related('items__producto').all().order_by('-fecha')
    return render(request, 'tienda/ventas_historial.html', {'ventas': ventas})

@login_required
def ventas_detalle(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    items = venta.items.all()
    return render(request, 'tienda/ventas_detalle.html', {'venta': venta})


# ---------------------------
# CRUD VENDEDORES
# ---------------------------
@login_required
def vendedores_list(request):
    vendedores = Vendedor.objects.all()
    return render(request, 'tienda/vendedores_list.html', {'vendedores': vendedores})

@login_required
def vendedores_create(request):
    if request.method == 'POST':
        form = VendedorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('vendedores_list')
    else:
        form = VendedorForm()
    return render(request, 'tienda/vendedores_form.html', {'form': form})

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
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next') or 'inicio'
            return redirect(next_url)
        else:
            messages.error(request, "Usuario o contraseña incorrecta")
    return render(request, 'tienda/login.html')

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

        cliente = Cliente.objects.create(nombre=nombre, correo=correo, telefono=telefono)
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
