from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


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

    def __str__(self):
        return self.nombre

# ----------------------------
# Vendedor
# ----------------------------

# ----------------------------
# Venta
# ----------------------------
class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
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
    def total(self):
        return sum([item.subtotal() for item in self.items.all()])

    def save(self, *args, **kwargs):
        if not self.factura_num:
            last = Venta.objects.all().order_by('id').last()
            last_num = int(last.factura_num.replace('FAC','')) if last and last.factura_num else 0
            self.factura_num = f"FAC{last_num+1:04d}"
        super().save(*args, **kwargs)

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
class Vendedor(AbstractUser):
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.username
    