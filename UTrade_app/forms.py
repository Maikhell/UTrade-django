from django import forms
from .models import Product, User, Services
from django.contrib.auth.forms import UserCreationForm , AuthenticationForm

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'description',
            'price',
            'stocks',
            'image',
            'category',
            
        ]
        widgets = {
            'description': forms.Textarea(attrs={'cols': 80, 'rows': 5})
        }
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Services
        fields = ['name', 'description', 'category', 'base_price', 'turnaround_time']        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Service Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'turnaround_time': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3-5 days'}),
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
    
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'display_name', 'phone_number', 'student_no', 'image', 'course', 'section']
        widgets = {
            'image': forms.FileInput(attrs={'id': 'id_profile_picture', 'class': 'd-none', 'onchange': 'previewAvatar(event)'}),
        }
class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # update the label so the user knows to enter their Student No
        self.fields['username'].label = "Student Number"
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Enter Student Number'
        })
    
    
class UserAccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['student_no']


        