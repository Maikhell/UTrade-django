from django import forms
from .models import Product, User, Services
from django.contrib.auth.forms import UserCreationForm , AuthenticationForm

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'description',
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
        
class UserRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['student_no', 'email'] 

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data
    def clean_student_no(self):
        student_no = self.cleaned_data.get('student_no')
        if User.objects.filter(student_no=student_no).exists():
            raise forms.ValidationError("This student number is already registered. Try logging in.")
        return student_no

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save() 
        return user
    
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


        