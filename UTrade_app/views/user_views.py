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
from ..utils import send_otp_email

class UserCreateView(CreateView):
    model = User 
    form_class = UserRegistrationForm
    template_name = 'UTrade_app/users/account/register.html'
    success_url = reverse_lazy('verify_otp') 
    
    def form_valid(self, form):
        user = form.save(commit=False)
        
        chosen_role = self.request.POST.get('user_role', 'student')
        user.user_role = chosen_role if chosen_role in ['student', 'alumni'] else 'student'
        user.is_active = False 
        user.status = 'unverified'
        
        user.save()
        
        self.request.session['pending_user_id'] = user.id
        self.request.session.modified = True
        self.request.session.save() 
        
        try:
            send_otp_email(user)
            messages.info(self.request, "A verification code has been sent to your CVSU email.")
        except Exception as e:
            print(f"SMTP/Email Error: {e}")
            messages.warning(self.request, "Account created, but we had trouble sending the email.")

        return redirect('/verify-email/')

    def form_invalid(self, form):
        print(f"Form Validation Errors: {form.errors}")
        return super().form_invalid(form)
    
class UserAccountView(TemplateView):
    template_name = 'UTrade_app/users/account/accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.is_authenticated:
            context['incoming_orders_count'] = Order.objects.filter(
                items__product_variant__product__seller=self.request.user,
                status='Pending'
            ).distinct().count()
        else:
            context['incoming_orders_count'] = 0
            
        return context
class UserProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'UTrade_app/users/account/profile.html'
    success_url = reverse_lazy('user.profile')
    success_message = "Your profile has been updated successfully!" 

    def get_object(self):
        return self.request.user

    def post(self, request, *args, **kwargs):
        """
        Explicitly handle the POST request to ensure manual HTML 
        inputs are captured by the form.
        """
        self.object = self.get_object()
        form = self.get_form()
        
        if form.is_valid():
            return self.form_valid(form)
        else:
            # Debugging: This will show you EXACTLY why it didn't save in your terminal
            print("Form Errors:", form.errors)
            messages.error(self.request, "Validation failed. Please check your inputs.")
            return self.form_invalid(form)

    def form_valid(self, form):
        if 'image' in self.request.FILES:
            form.instance.image = self.request.FILES['image']

        # Sync Display Name to Username
        display_name = form.cleaned_data.get('display_name')
        if display_name:
            if User.objects.filter(username=display_name).exclude(pk=self.request.user.pk).exists():
                messages.error(self.request, "Display name already taken.")
                return self.form_invalid(form)
            form.instance.username = display_name

        return super().form_valid(form)
            

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
def update_terms_agreement(request):
    if request.method == "POST":
        user = request.user
        user.has_agreed_to_terms = True
        user.save()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"}, status=400)

@login_required
def update_cor(request):
    if request.method == 'POST':
        user = request.user
        cor_file = request.FILES.get('cor_file')
        required_fields = [user.first_name, user.last_name, user.student_no, user.course, user.section]
        if not all(required_fields):
            messages.error(request, "Please complete your Profile (Name, Student No, Course, and Section) before uploading your COR.")
            return redirect('user.profile') # Adjust name to your edit profile URL

        if cor_file:
            user.cor_file = cor_file
            user.status = 'Pending' 
            user.save()
            if user.status == 'unverified':
                messages.success(request, "COR submitted! Admin will review your account soon.")
            else:
                messages.success(request, "Your COR has been updated and is now pending for re-verification.")
        else:
            messages.error(request, "Please select a file to upload.")

    return redirect('user.account')
@login_required
def register_officer(request):
    if request.method == 'POST':
        user = request.user
        
        organization = request.POST.get('organization')
        position = request.POST.get('position')
        officer_id_image = request.FILES.get('officer_id_image')

        if organization and position and officer_id_image:
            user.organization = organization
            user.position = position
            user.officer_id_image = officer_id_image
            user.officer_status = 'pending'
            user.save()

            messages.success(request, "Officer application submitted! Please wait for admin verification.")
        else:
            messages.error(request, "Please fill in all fields and upload your ID.")
            
        return redirect('user.profile')
    
    return redirect('user.account')