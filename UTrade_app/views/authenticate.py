from django.shortcuts import redirect, render
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.contrib import messages
from ..forms import UserLoginForm

class Login(LoginView):
    authentication_form = UserLoginForm
    template_name = 'UTrade_app/users/account/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('product.list')
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Welcome Back, {self.request.user.student_no}!")        
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid Student No or Password')
        return super().form_invalid(form)
    
class Logout(LogoutView):
    next_page = reverse_lazy('landingpage')