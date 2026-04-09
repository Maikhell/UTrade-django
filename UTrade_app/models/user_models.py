from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.templatetags.static import static

def user_profile_path(instance, filename):
    return f'profiles/student_{instance.student_no}/{filename}'

class User(AbstractUser):
    username = models.CharField(max_length=70, blank=True, null=True)
    student_no = models.CharField(
        max_length=20, 
        unique=True, 
        validators=[RegexValidator(r'^\d+$', "Student number must be numeric")]
    )
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('alumni', 'Alumni'),
        ('staff', 'University Staff'),
    ]
    
    user_role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='student'
    )
    email = models.EmailField(unique=True) 
    
    cor_file = models.ImageField(
        upload_to=user_profile_path, 
        blank=True, 
        null=True, 
        verbose_name='COR_file'
    )

    course = models.CharField(max_length=100, blank=True, null=True,)
    section = models.CharField(max_length=30, blank=True, null=True,) 
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(max_length=20, default='unverified')
    
    display_name = models.CharField(max_length=150, blank=True, null=True, unique=True)
    image = models.ImageField(
        upload_to=user_profile_path, 
        blank=True, 
        null=True, 
        verbose_name='Profile Picture'
    )
    
    USERNAME_FIELD = 'student_no'
    REQUIRED_FIELDS = ['email', 'username']
    
    @property
    def profile_pic_url(self):
        try:
            if self.image and self.image.url:
                return self.image.url
        except ValueError:
            pass
        return static('UTrade_app/img/default-user.png')
    @property
    def get_short_name(self):
        if self.display_name and self.display_name.strip():
            return self.display_name
        if self.username and self.username.strip():
            return self.username
        if self.student_no:
            return str(self.student_no)
        return f"User_{self.id}" 
    def __str__(self):
        return str(self.get_short_name)