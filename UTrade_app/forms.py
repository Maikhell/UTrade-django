from django import forms
from .models import Product, User, Services, ProductVariant, ProductImage
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'pre_order', 'accepted_payments','owner_type']
        widgets = {
            'description': forms.Textarea(attrs={'cols': 80, 'rows': 5, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'pre_order': forms.Select(
                choices=[(False, 'Live (On-hand Stock)'), (True, 'Pre-order (Advance Order)')],
                attrs={'class': 'form-select'}
            ),
            'accepted_payments': forms.Select(attrs={'class': 'form-select'}),
        }
class VariantForm(forms.ModelForm):
    """Form specifically for adding/editing product variations"""
    assigned_image = forms.ModelChoiceField(
        queryset=ProductImage.objects.none(), 
        required=False,
        label="Variant Photo",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = ProductVariant
        fields = ['variant_name', 'price', 'stocks']
        widgets = {
            'variant_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Small, Red'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'stocks': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)
        if product:
            self.fields['assigned_image'].queryset = ProductImage.objects.filter(product=product)


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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Get the role from the POST data directly
        role = self.data.get('user_role')

        if email:
            email = email.lower()
            
            # Validation for Student accounts
            if role == 'student':
                if not email.endswith('@cvsu.edu.ph'):
                    raise forms.ValidationError(
                        "Students are required to use their official @cvsu.edu.ph email."
                    )
            
            # General uniqueness check
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError("This email is already registered.")
        
        return email

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
            raise forms.ValidationError("This student number is already registered.")
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
        # Ensure 'image' matches your Model field name (e.g., profile_picture)
        fields = ['first_name', 'last_name', 'display_name', 'phone_number', 'student_no', 'image', 'course', 'section']
        widgets = {
            'image': forms.FileInput(attrs={'id': 'id_profile_picture', 'class': 'd-none', 'onchange': 'previewAvatar(event)'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control rounded-3'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control rounded-3'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control rounded-3'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control rounded-3'}),
            'student_no': forms.TextInput(attrs={'class': 'form-control rounded-3'}),
            'course': forms.Select(attrs={'class': 'form-select rounded-3'}), # Use Select for course
            'section': forms.TextInput(attrs={'class': 'form-control rounded-3', 'maxlength': '3'}),
        }

    def __init__(self, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        
        # Set optional fields
        optional_fields = ['student_no', 'course', 'section', 'phone_number', 'display_name']
        for field in optional_fields:
            self.fields[field].required = False
            
        # Logic for Student requirements
        if self.instance and self.instance.pk:
            if getattr(self.instance, 'user_role', None) == 'student':
                self.fields['student_no'].required = True
                self.fields['course'].required = True
                self.fields['section'].required = True
                
class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Student Number"
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter Student Number'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control'
        })

class UserAccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['student_no']
        widgets = {'student_no': forms.TextInput(attrs={'class': 'form-control'})}