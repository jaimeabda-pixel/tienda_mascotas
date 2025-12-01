from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView, LoginView
from . import views

urlpatterns = [
    # Inicio y autenticación
    path('', login_required(views.inicio), name='inicio'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registrar-vendedor/', views.registrar_vendedor, name='registrar_vendedor'),

    # Productos
    path('productos/', views.productos_list, name='productos_list'),
    path('productos/crear/', views.productos_create, name='productos_create'),
    path('productos/<int:pk>/editar/', views.productos_update, name='productos_update'),
    path('productos/<int:pk>/eliminar/', views.productos_delete, name='productos_delete'),

    # Clientes
    path('clientes/', views.clientes_list, name='clientes_list'),
    path('clientes/crear/', views.clientes_create, name='clientes_create'),
    path('clientes/<int:pk>/editar/', views.clientes_update, name='clientes_update'),
    path('clientes/<int:pk>/eliminar/', views.clientes_delete, name='clientes_delete'),
    path('cliente/add/ajax/', views.cliente_add_ajax, name='cliente_add_ajax'),

    # Vendedores
    path('vendedores/', views.vendedores_list, name='vendedores_list'),
    path('vendedores/crear/', views.vendedores_create, name='vendedores_create'),
    path('vendedores/<int:pk>/editar/', views.vendedores_update, name='vendedores_update'),
    path('vendedores/<int:pk>/eliminar/', views.vendedores_delete, name='vendedores_delete'),

    # Ventas
    path('ventas/', views.ventas_list, name='ventas_list'),
    path('ventas/crear/', views.ventas_create, name='ventas_create'),
    path('ventas/crear/<int:producto_id>/', views.ventas_create, name='ventas_create_producto'),
    path('ventas/<int:pk>/eliminar/', views.ventas_delete, name='ventas_delete'),
    path('ventas/<int:pk>/factura/', views.ventas_factura_pdf_rl, name='ventas_factura_pdf_rl'),
    path('ventas/historial/', views.ventas_historial, name='ventas_historial'),
    path('ventas/<int:pk>/detalle/', views.ventas_detalle, name='ventas_detalle'),

    # Punto de venta (POS)
    path('ventas/pos/', views.ventas_pos, name='ventas_pos'),
    path('ventas/pos/register/', views.ventas_pos_register, name='ventas_pos_register'),
    path('ventas/pos/codigo/', views.ventas_pos_producto_codigo, name='ventas_pos_producto_codigo'),
    path('ventas/producto/codigo/', views.ventas_pos_producto_codigo, name='ventas_pos_producto_codigo'),

    # Páginas estáticas
    path('contacto/', views.contacto, name='contacto'),
    path('acerca/', views.acerca, name='acerca'),
    path('productos/buscar-htmx/', views.buscar_productos_htmx, name='buscar_productos_htmx'),
    path('perfil/', views.perfil, name='perfil'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('notificaciones/', views.notificaciones, name='notificaciones'),
    path('graficos/', views.graficos, name='graficos'),

]
