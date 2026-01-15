from django.views.generic import ListView, CreateView, DeleteView, DetailView, UpdateView
from ..models import User
from django.urls import reverse_lazy
from django.contrib.auth import login
from ..forms import UserRegistrationForm

class UserCreateView(CreateView):
    model = User 
    form_class = UserRegistrationForm
    template_name = 'UTrade_app/users/account/register.html'
    success_url = reverse_lazy('product.list')
    
    def form_valid(self,form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
    