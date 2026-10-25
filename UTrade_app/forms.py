import re
from django import forms
from django.db.models import Q
from .models import Product, User, ProductVariant, ProductImage
from .utils import is_allowed_email, is_pending_verification
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'pre_order', 'accepted_payments', 'owner_type']
        widgets = {
            'description': forms.Textarea(attrs={'cols': 80, 'rows': 5, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'pre_order': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
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
            
            # Students may register with a Gmail or an official @cvsu.edu.ph address
            if role == 'student':
                if not is_allowed_email(email):
                    raise forms.ValidationError(
                        "Please use a Gmail or official @cvsu.edu.ph email address."
                    )
            
            # General uniqueness check
            existing = User.objects.filter(email__iexact=email).first()
            if existing:
                if is_pending_verification(existing):
                    raise forms.ValidationError(
                        "This email is registered but not verified yet. "
                        "Sign in with your student number and password to get a new code."
                    )
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
        student_no = (self.cleaned_data.get('student_no') or '').strip()

        # Digits only, exactly 9 characters (no letters, symbols, or spaces)
        if not re.fullmatch(r'[0-9]{9}', student_no):
            raise forms.ValidationError("Student number must be exactly 9 digits.")

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
    # Set to True when the credentials belong to an account that never finished OTP verification
    pending_verification = False

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

    def clean(self):
        username = (self.cleaned_data.get('username') or '').strip()
        password = self.cleaned_data.get('password')

        if username and password:
            pending = self._pending_user(username, password)
            if pending is not None:
                # Correct password, but the email was never verified. Hand them to the OTP step.
                self.pending_verification = True
                if self.request is not None:
                    session = self.request.session
                    session['pending_user_id'] = pending.id
                    session.pop('otp_sent', None)
                    session.pop('otp_attempts', None)
                raise forms.ValidationError(
                    "Your email isn't verified yet. We'll take you to the verification page.",
                    code='email_unverified',
                )

        return super().clean()

    @staticmethod
    def _pending_user(identifier, password):
        """Unverified account matching these credentials (password is checked first)."""
        candidates = User.objects.filter(
            Q(student_no__iexact=identifier)
            | Q(email__iexact=identifier)
            | Q(username__iexact=identifier),
            is_active=False,
        )[:5]
        for candidate in candidates:
            if is_pending_verification(candidate) and candidate.check_password(password):
                return candidate
        return None

class UserAccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['student_no']
        widgets = {'student_no': forms.TextInput(attrs={'class': 'form-control'})}