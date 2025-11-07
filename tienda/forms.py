from django import forms
from .models import Producto, Cliente, Venta, VentaItem, Vendedor
from django.contrib.auth.forms import UserCreationForm


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['codigo_barras', 'nombre', 'descripcion', 'precio', 'stock', 'imagen']
        widgets = {
            'codigo_barras': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Código de barras'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'precio': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
        }

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'correo', 'telefono', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class VentaForm(forms.ModelForm):
    class Meta:
        model = Venta
        fields = ['cliente', 'metodo_pago', 'efectivo_recibido']

class VentaItemForm(forms.ModelForm):
    class Meta:
        model = VentaItem
        fields = ['producto', 'cantidad']
        widgets = {
            'producto': forms.Select(attrs={'class':'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class':'form-control', 'min':1})
        }

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        producto = self.cleaned_data.get('producto')
        if producto and cantidad:
            if cantidad > producto.stock:
                raise forms.ValidationError(f"No hay suficiente stock de {producto.nombre}. Stock disponible: {producto.stock}")
        return cantidad

    def save(self, commit=True):
        venta_item = super().save(commit=False)
        venta_item.precio_unitario = venta_item.producto.precio
        if commit:
            venta_item.save()
        # Actualiza stock
        venta_item.producto.stock -= venta_item.cantidad
        venta_item.producto.save()
        return venta_item

# ----------------------------
# Formularios para Vendedor
# ----------------------------
class VendedorForm(forms.ModelForm):
    class Meta:
        model = Vendedor
        fields = ['username', 'email', 'first_name', 'last_name']  # campos existentes en AbstractUser
        widgets = {
            'username': forms.TextInput(attrs={'class':'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'first_name': forms.TextInput(attrs={'class':'form-control'}),
            'last_name': forms.TextInput(attrs={'class':'form-control'}),
        }

class VendedorRegistroForm(UserCreationForm):
    class Meta:
        model = Vendedor
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class':'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'first_name': forms.TextInput(attrs={'class':'form-control'}),
            'last_name': forms.TextInput(attrs={'class':'form-control'}),
            'password1': forms.PasswordInput(attrs={'class':'form-control'}),
            'password2': forms.PasswordInput(attrs={'class':'form-control'}),
        }