from django import forms
from .models import Products, User
from django.contrib.auth.forms import UserCreationForm

class ProductForm(forms.ModelForm):
    class Meta:
        model = Products
        fields = [
            'product_name',
            'product_description',
            'product_price',
            'product_quantity',
            'product_rating',
            'product_image',
        ]
        widgets = {
            'product_description': forms.Textarea(attrs={'cols': 80, 'rows': 5})
        }
        
class UserRegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("student_no", "email") 
    #to make sure the student_no field is cleaned properly:
    def clean_student_no(self):
        student_no = self.cleaned_data.get('student_no')
        if not student_no:
            raise forms.ValidationError("Student number is required.")
        return student_no
    
class UserAccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['student_no']
        