from django.views.generic import ListView, CreateView, DeleteView, DetailView, UpdateView, TemplateView
from ..models import User, Product
from django.urls import reverse_lazy
from django.contrib.auth import login
from ..forms import UserRegistrationForm, UserProfileForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.contrib import messages

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
    form_class = UserProfileForm
    template_name = 'UTrade_app/users/account/profile.html'
    success_url = reverse_lazy('user.profile')
    
    def get_object(self):
        return self.request.user
    def form_valid(self, form):
        #Added Success Message
        messages.success(self.request, "Your profile has been updated successfully!")
        return super().form_valid(form)
    
class UserProductsView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'UTrade_app/users/account/seller_inventory.html'
    context_object_name = 'products'

    def get_queryset(self):
        # Single query with annotations to get all counts at once
        return Product.objects.filter(seller=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
    
        #Much faster than running .filter().count() three times
        counts = Product.objects.filter(seller=self.request.user).aggregate(
            approved=Count('id', filter=Q(status='Approved')),
            pending=Count('id', filter=Q(status='Pending')),
            rejected=Count('id', filter=Q(status='Rejected'))
        )
        context.update({
            'approved_count': counts['approved'],
            'pending_count': counts['pending'],
            'rejected_count': counts['rejected'],
        })
        return context
    