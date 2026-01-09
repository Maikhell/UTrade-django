from django import forms
from .models import Products


class ProductForm(forms.ModelForm):
    class Meta:
        fields = [
            'product_name'
            'product_description'
            'product_price'
            'product_quantity'
            'product_rating'
            'product_image'
        ]
        widgets = {
            'product_description': forms.Textarea(attrs={'cols': 80, 'rows': 5})
        }