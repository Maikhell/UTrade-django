from django import forms
from .models import Products, User, Services
from django.contrib.auth.forms import UserCreationForm , AuthenticationForm

class ProductForm(forms.ModelForm):
    class Meta:
        model = Products
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
        fields = ['turnaround_time']
        widgets = {
            'turnaround_time': forms.TextInput(attrs={'placeholder': '3-5 days'}),
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


        