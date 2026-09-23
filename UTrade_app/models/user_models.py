from django.contrib.auth.models import AbstractUser 
from django.db import models
from .organization_models import Organization
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
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
        ('alumni', 'Alumni'),
        ('system_admin', 'System Admin'), 
        ('campus_admin', 'Campus Admin'),
        ('org_officer', 'Organization Officer'),
        ('alumni_assoc', 'Alumni Association'),
        ('management', 'Management'),
    ]
    
    user_role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='student'
    )
    email = models.EmailField(
        unique=True, 
    ) 

    is_email_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    
    cor_file = models.ImageField(
        upload_to=user_profile_path, 
        blank=True, 
        null=True, 
        verbose_name='COR_file'
    )
    is_suspended = models.BooleanField(default=False)
    suspension_until = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)
    has_agreed_to_terms = models.BooleanField(default=False)
    course = models.CharField(max_length=100, blank=True, null=True,)
    section = models.CharField(max_length=30, blank=True, null=True,) 
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(max_length=20, default='unverified')
    is_officer = models.BooleanField(default=False)
    officer_status = models.CharField(
        max_length=20, 
        choices=[('unverified', 'Unverified'), ('pending', 'Pending'), ('verified', 'Verified')],
        default='unverified'
    )
    organization = models.CharField(max_length=50, blank=True, null=True)  
    org_link = models.ForeignKey(
        'Organization', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="members"
    )
    position = models.CharField(max_length=50, blank=True, null=True)
    officer_id_image = models.ImageField(upload_to='officer_ids/', blank=True, null=True)
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
class Conversation(models.Model):

    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_chats')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_chats')
    created_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.user.username}: {self.content[:20]}"
    
# models.py (or messaging models)
class UserReport(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    REASON_CHOICES = [
        ('Harassment', 'Harassment / Abuse'),
        ('Spam', 'Spam / Scam'),
        ('Inappropriate', 'Inappropriate content'),
        ('Threats', 'Threats / Intimidation'),
        ('Impersonation', 'Impersonation'),
        ('Other', 'Other'),
    ]

    conversation = models.ForeignKey(
        'Conversation', on_delete=models.CASCADE, related_name='reports'
    )
    reporter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reports_filed'
    )
    reported_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reports_against'
    )
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports_reviewed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Report #{self.id} on {self.reported_user} by {self.reporter}"