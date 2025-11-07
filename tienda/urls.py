"""
URL configuration for tienda_mascotas project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', login_required(views.inicio), name='inicio'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    

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

    # Ventas
    path('ventas/', views.ventas_list, name='ventas_list'),
    path('ventas/crear/', views.ventas_create, name='ventas_create'),
    path('ventas/crear/<int:producto_id>/', views.ventas_create, name='ventas_create_producto'),
    path('ventas/<int:pk>/eliminar/', views.ventas_delete, name='ventas_delete'),
    path('ventas/<int:pk>/factura/', views.ventas_factura_pdf_rl, name='ventas_factura_pdf_rl'),
    path('cliente/add/ajax/', views.cliente_add_ajax, name='cliente_add_ajax'),

    # vendedor
    path('vendedores/', views.vendedores_list, name='vendedores_list'),
    path('vendedores/crear/', views.vendedores_create, name='vendedores_create'),


    # Estáticas
    path('contacto/', views.contacto, name='contacto'),
    path('acerca/', views.acerca, name='acerca'),
    # Historial y detalle de ventas
    path('ventas/historial/', views.ventas_historial, name='ventas_historial'),
    path('ventas/<int:pk>/detalle/', views.ventas_detalle, name='ventas_detalle'),
    
    
    path('login/', auth_views.LoginView.as_view(template_name='tienda/login.html'), name='login'),
    path('registrar-vendedor/', views.registrar_vendedor, name='registrar_vendedor'),
    path('ventas/pos/', views.ventas_pos, name='ventas_pos'),
    path('ventas/pos/register/', views.ventas_pos_register, name='ventas_pos_register'),
    path('ventas/pos/codigo/', views.ventas_pos_producto_codigo, name='ventas_pos_producto_codigo'),
    path('ventas/producto/codigo/', views.ventas_pos_producto_codigo, name='ventas_pos_producto_codigo'),



]

