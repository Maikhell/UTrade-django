from django.shortcuts import redirect, render
from django.contrib.auth.views import LoginView


class Login(LoginView):
    template_name = 'UTrade_app/users/account/login.html'
    