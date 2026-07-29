from django.shortcuts import redirect
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.contrib import messages
from ..forms import UserLoginForm
from django.contrib.auth import authenticate, login
from ..models import User


from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model

User = get_user_model()


class Login(LoginView):
    authentication_form = UserLoginForm
    template_name = 'UTrade_app/accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('product.list')

    def post(self, request, *args, **kwargs):
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not identifier or not password:
            messages.error(request, "Please fill in all fields.")
            return self.render_to_response(self.get_context_data())

        # Look up user by student_no or username
        user_obj = User.objects.filter(
            Q(student_no__iexact=identifier) | Q(username__iexact=identifier)
        ).first()

        if not user_obj:
            messages.error(request, "Invalid credentials.")
            return self.render_to_response(self.get_context_data())

        # Authenticate using the retrieved user's student_no
        user = authenticate(
            request,
            student_no=user_obj.student_no,
            password=password
        )

        if user is None:
            messages.error(request, "Invalid credentials.")
            return self.render_to_response(self.get_context_data())

        # Perform login and display welcome message
        login(request, user)
        name = user.first_name if user.first_name else (user.username or user.student_no)
        messages.success(request, f"Welcome Back, {name}!")

        return redirect(self.get_success_url())

class Logout(LogoutView):
    next_page = reverse_lazy('landingpage')