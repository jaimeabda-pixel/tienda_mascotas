from django.contrib import admin
from .models import Producto, Cliente, Venta, VentaItem, Vendedor

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'stock', 'codigo_barras')   # ← línea limpia
    list_editable = ('precio', 'stock')
    search_fields = ('nombre', 'codigo_barras')

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono')
    search_fields = ('nombre', 'correo')

class VentaItemInline(admin.TabularInline):
    model = VentaItem
    extra = 0

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('factura_num', 'cliente', 'fecha', 'total')
    list_filter = ('fecha', 'metodo_pago')
    inlines = [VentaItemInline]
    readonly_fields = ('total', 'fecha', 'factura_num')

@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'email')