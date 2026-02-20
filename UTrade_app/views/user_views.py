from django.views.generic import ListView, CreateView, DeleteView, DetailView, UpdateView, TemplateView
from ..models import User, Product
from django.urls import reverse_lazy
from django.contrib.auth import login
from ..forms import UserRegistrationForm
from django.contrib.auth.mixins import LoginRequiredMixin

class UserCreateView(CreateView):
    model = User 
    form_class = UserRegistrationForm
    template_name = 'UTrade_app/users/account/register.html'
    success_url = reverse_lazy('product.list')
    
    def form_valid(self,form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
    
class UserAccountView(TemplateView):
    template_name = 'UTrade_app/users/account/accounts.html'
   
class UserProfileView(LoginRequiredMixin, UpdateView):
    model = User
    template_name = 'UTrade_app/users/account/profile.html'
    fields = ['first_name', 'last_name', 'display_name', 'number', 'student_no', 'image' ]
    success_url = '/userprofile/'
    
    def get_object(self):
        return self.request.user
    
class UserProductsView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'UTrade_app/users/account/seller_inventory.html'
    context_object_name = 'products'

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user).order_by('-created_at')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_products = self.get_queryset()
        context['Approved_count'] = user_products.filter(status = 'Approved').count()
        context['Pending_count'] = user_products.filter(status = 'Pending').count()
        context['Rejected_count'] = user_products.filter(status = 'Rejected').count()
        return context

    