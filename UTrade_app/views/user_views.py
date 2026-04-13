from django.views.generic import ListView, CreateView, DeleteView, DetailView, UpdateView, TemplateView
from ..models import User, Product, Order, MeetupLocation
from django.urls import reverse_lazy
from ..forms import UserRegistrationForm, UserProfileForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Q
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.http import JsonResponse



class UserCreateView(CreateView):
    model = User 
    form_class = UserRegistrationForm
    template_name = 'UTrade_app/users/account/register.html'
    success_url = reverse_lazy('product.list')
    
    def form_valid(self, form):
        user = form.save()
        self.object = user 
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(self.request, "Welcome! Your account was created.")
        return redirect(self.get_success_url())
    
class UserAccountView(TemplateView):
    template_name = 'UTrade_app/users/account/accounts.html'
   
class UserProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'UTrade_app/users/account/profile.html'
    success_url = reverse_lazy('user.profile')
    success_message = "Your profile has been updated successfully!" 
    
    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        display_name = form.cleaned_data.get('display_name')
        if display_name:
            if User.objects.filter(username=display_name).exclude(pk=self.request.user.pk).exists():
                messages.error(self.request, "That display name is already taken. Please choose another.")
                return self.form_invalid(form)
            
            form.instance.username = display_name
        return super().form_valid(form)
            
        return super().form_valid(form)

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from ..models import Product, Order, MeetupLocation

class UserProductsView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'UTrade_app/users/account/seller_inventory.html'
    context_object_name = 'products'

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        counts = Product.objects.filter(seller=user).aggregate(
            approved=Count('id', filter=Q(status='Approved')),
            pending=Count('id', filter=Q(status='Pending')),
            rejected=Count('id', filter=Q(status='Rejected'))
        )
        
        incoming_orders = Order.objects.filter(
            seller=user
        ).filter(
            Q(status='Pending') | Q(status='Paid')
        ).order_by('-created_at')

        accepted_orders = Order.objects.filter(
            seller=user,
            status='Accepted'
        ).order_by('-created_at')

        completed_orders = Order.objects.filter(
            seller=user, 
            status='Completed'
        ).order_by('-updated_at')
        
        locations = MeetupLocation.objects.filter(is_active=True).order_by('name')
        
        context.update({
            'approved_count': counts['approved'],
            'pending_count': counts['pending'],
            'rejected_count': counts['rejected'],
            'incoming_orders': incoming_orders, 
            'incoming_count': incoming_orders.count(),
            'accepted_orders': accepted_orders,
            'accepted_count': accepted_orders.count(),
            'completed_orders': completed_orders,
            'completed_count': completed_orders.count(),
            'locations': locations, 
        })
        
        return context

class ProductUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Product
    fields = ['name', 'description', 'category'] 
    template_name = 'UTrade_app/users/account/edit_product.html'
    success_url = reverse_lazy('seller_inventory')
    success_message = "Product updated successfully!"

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user)

    def form_valid(self, form):
        form.instance.status = 'Pending'
        
        form.instance.seller = self.request.user
        
        messages.info(self.request, "Product changes saved! It is now pending admin review before going live again.")
        
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from ..models import MeetupLocation # Local import to avoid circular issues
        context['locations'] = MeetupLocation.objects.filter(is_active=True)
        return context

class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    success_url = reverse_lazy('seller_inventory')

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user)

    def delete(self, request, *args, **kwargs):
        product = self.get_object()
        messages.success(request, f"Listing for '{product.name}' was successfully removed.")
        return super().delete(request, *args, **kwargs)  
@login_required
def submit_verification(request):
    if request.method == 'POST':
        cor_file = request.FILES.get('cor_file')
        user = request.user
        
        # Validation check
        if not all([user.first_name, user.last_name, user.student_no, user.course, user.section]):
            messages.error(request, "Please complete your profile before verifying.")
            return redirect('user.profile')

        if cor_file:
            user.cor_file = cor_file 
            user.status = 'Pending' 
            user.save()
            messages.success(request, "COR submitted! Admin will review your account.")
            
    return redirect('user.account')
@login_required
def update_terms_agreement(request):
    if request.method == "POST":
        user = request.user
        user.has_agreed_to_terms = True
        user.save()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"}, status=400)