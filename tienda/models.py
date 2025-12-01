from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from decimal import Decimal


# ----------------------------
# Producto
# ----------------------------
class Producto(models.Model):
    codigo_barras = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)

    def __str__(self):
        return self.nombre

# ----------------------------
# Cliente
# ----------------------------
class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='clientes')

    def __str__(self):
        return self.nombre

# ----------------------------
# Vendedor
# ----------------------------
class Vendedor(AbstractUser):
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    foto_perfil = models.ImageField(upload_to='perfiles/', blank=True, null=True)
    
    # Nuevos campos para gestión de vendedores
    comision_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Porcentaje de comisión (0-100)")
    meta_mensual = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Meta de ventas mensual")

    def __str__(self):
        return self.username

# ----------------------------
# Venta
# ----------------------------
class Venta(models.Model):
    ESTADOS = [
        ('Pendiente', 'Pendiente'),
        ('Pagada', 'Pagada'),
        ('Cancelada', 'Cancelada'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=20, choices=[('Efectivo','Efectivo'),('Tarjeta','Tarjeta')], default='Efectivo')
    efectivo_recibido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vuelto = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    factura_num = models.CharField(max_length=20, unique=True, blank=True, null=True)
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Nuevos campos
    estado = models.CharField(max_length=20, choices=ESTADOS, default='Pagada')
    comision_monto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notas = models.TextField(blank=True, null=True)
    comprobante_pago = models.ImageField(upload_to='comprobantes/', blank=True, null=True)
    
    def total(self):
        return sum([item.subtotal() for item in self.items.all()])

    def save(self, *args, **kwargs):
        if not self.factura_num:
            last = Venta.objects.all().order_by('id').last()
            last_num = int(last.factura_num.replace('FAC','')) if last and last.factura_num else 0
            self.factura_num = f"FAC{last_num+1:04d}"
        
        super().save(*args, **kwargs)

    def actualizar_comision(self):
        """Método helper para recalcular comisión después de agregar items"""
        if self.vendedor and self.vendedor.comision_porcentaje > 0:
            total_venta = self.total()
            self.comision_monto = (total_venta * self.vendedor.comision_porcentaje) / 100
            self.save()

# ----------------------------
# VentaItem: Productos de una venta
# ----------------------------
class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, related_name='items', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        if not self.pk:
            self.precio_unitario = self.producto.precio
            if self.cantidad > self.producto.stock:
                raise ValueError(f"No hay suficiente stock de {self.producto.nombre}")
            self.producto.stock -= self.cantidad
            self.producto.save()
        super().save(*args, **kwargs)
        
        # Actualizar comisión de la venta padre
        self.venta.actualizar_comision()