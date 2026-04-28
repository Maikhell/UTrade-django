from django.shortcuts import redirect, render
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.contrib import messages
from ..forms import UserLoginForm
from django.contrib.auth import authenticate, login
from ..models import User


class Login(LoginView):
    authentication_form = UserLoginForm
    template_name = 'UTrade_app/users/account/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('product.list')

    def post(self, request, *args, **kwargs):
        identifier = request.POST.get('username')
        password = request.POST.get('password')
        mode = request.POST.get('login_mode')

        if not identifier or not password:
            messages.error(request, "Please fill in all fields.")
            return self.render_to_response(self.get_context_data())

        user = None

        if mode == 'student':
            user = authenticate(
                request,
                student_no=identifier,
                password=password
            )

            if user is None:
                messages.error(request, "Invalid Student Number or password.")
                return self.render_to_response(self.get_context_data())

        else:
            user_obj = User.objects.filter(username=identifier).first()

            if not user_obj:
                messages.error(request, "Username not found.")
                return self.render_to_response(self.get_context_data())

            user = authenticate(
                request,
                student_no=user_obj.student_no,  
                password=password
            )

            if user is None:
                messages.error(request, "Invalid username or password.")
                return self.render_to_response(self.get_context_data())

        if user is not None:
            if mode == 'mgmt':
                allowed_roles = ['management', 'admin', 'officer', 'campus_admin','alumni_assoc']
                if not user.is_superuser and (not user.is_staff and user.user_role not in allowed_roles):
                    messages.error(request, "Access denied. This is not a staff account.")
                    return self.render_to_response(self.get_context_data())

            login(request, user)

            name = user.first_name if user.first_name else user.username or user.student_no
            messages.success(request, f"Welcome, {name}!")
            return redirect(self.get_success_url())

        messages.error(request, "Invalid credentials.")
        return self.render_to_response(self.get_context_data())


class Logout(LogoutView):
    next_page = reverse_lazy('landingpage')