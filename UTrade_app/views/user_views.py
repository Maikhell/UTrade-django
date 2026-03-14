from django.views.generic import ListView, CreateView, DeleteView, DetailView, UpdateView, TemplateView
from ..models import User, Product
from django.urls import reverse_lazy
from django.contrib.auth import login
from ..forms import UserRegistrationForm, UserProfileForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Q
from django.contrib import messages
from django.shortcuts import redirect

class UserCreateView(CreateView):
    model = User 
    form_class = UserRegistrationForm
    template_name = 'UTrade_app/users/account/register.html'
    success_url = reverse_lazy('product.list')
    
    def form_valid(self,form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"Welcome {user.student_no}! Your account was created successfully.")
        return redirect(self.success_url)    
class UserAccountView(TemplateView):
    template_name = 'UTrade_app/users/account/accounts.html'
   
class UserProfileView(LoginRequiredMixin,SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'UTrade_app/users/account/profile.html'
    success_url = reverse_lazy('user.profile')
    success_message = "Your profile has been updated successfully!" 
    
    def get_object(self):
        return self.request.user
    
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
    