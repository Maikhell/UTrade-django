from django import forms
from .models import Products, User, UserProfile
from django.contrib.auth.forms import UserCreationForm

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
class UserAccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        
class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta(UserCreationForm.Meta):
        model = User
    fields = UserCreationForm.Meta.fields + ('email',)