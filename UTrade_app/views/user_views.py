from django.views.generic import ListView, CreateView, DeleteView, DetailView, UpdateView, TemplateView
from ..models import User, Product, Order, MeetupLocation,Organization,ProductVariant
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
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Count, Sum, Q

class UserCreateView(CreateView):
    model = User 
    form_class = UserRegistrationForm
    template_name = 'UTrade_app/accounts/register.html'
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
    template_name = 'UTrade_app/accounts/accounts.html'

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
    template_name = 'UTrade_app/accounts/profile.html'
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
        # Handle profile image upload
        if 'image' in self.request.FILES:
            form.instance.image = self.request.FILES['image']

        # Process Organization string (e.g., "ITS-BSIT")
        org_raw_text = form.cleaned_data.get('organization') 
        
        if org_raw_text:
            parts = [p.strip() for p in org_raw_text.split('-')]
            name_acronym = parts[0]
            course_code = parts[1] if len(parts) > 1 else ""

            org_map = {
                "ITS": "Information Technology Society",
                "CSG": "Central Student Government",
                "ACS": "Alliance of Computer Scientists",
                "HMS": "Hospitality Management Society",
                "LLP": "La Liga Psicologia",
                "LCDCS": "La Ciencia de Crimines Sociedad",
                "LMS-JMA": "Le Manager's Societe - Junior Marketing Association",
                "SHR": "Societas Humana Resource",
                "TES": "Teacher Education Society",
            }

            # get_or_create ensures the Org exists in your PostgreSQL database
            org_obj, created = Organization.objects.get_or_create(
                name=name_acronym,
                defaults={
                    'full_name': org_map.get(name_acronym, name_acronym),
                    'course_code': course_code
                }
            )
            
            # Explicitly link the organization object to the user instance
            form.instance.org_link = org_obj

        # Handle Display Name / Username change
        display_name = form.cleaned_data.get('display_name')
        if display_name:
            if User.objects.filter(username=display_name).exclude(pk=self.request.user.pk).exists():
                messages.error(self.request, "This display name is already taken by another student.")
                return self.form_invalid(form)
            form.instance.username = display_name

        # The super().form_valid(form) call saves the form.instance (the User) 
        # and includes the new org_link relationship.
        return super().form_valid(form)
            


@login_required
def order_delivered(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Security: make sure this order belongs to the current seller
    if not order.items.filter(product_variant__product__seller=request.user).exists():
        messages.error(request, "You are not allowed to update this order.")
        return redirect('seller.inventory')  # or your dashboard url name

    if request.method == 'POST':
        # Change status to Completed
        order.status = 'Completed'
        order.updated_at = timezone.now()
        order.save(update_fields=['status', 'updated_at'])

        # Optional: you can also set a delivered_at field if you have one
        # order.delivered_at = timezone.now()
        # order.save()

        messages.success(request, f"Order #{order.id} has been marked as Completed.")
        
        # TODO: send notification to buyer here if you have one

    return redirect('seller.inventory')  # change to your actual dashboard url name
class UserProductsView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'UTrade_app/seller/inventory.html'
    context_object_name = 'products'

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Product status counts
        counts = Product.objects.filter(seller=user).aggregate(
            approved=Count('id', filter=Q(status__iexact='Approved')),
            pending=Count('id', filter=Q(status__iexact='Pending')),
            rejected=Count('id', filter=Q(status__iexact='Rejected'))
        )

        # All orders that contain products of this seller
        seller_orders = Order.objects.filter(
            items__product_variant__product__seller=user
        ).distinct()

        incoming_orders = seller_orders.filter(
            Q(status__iexact='Pending') | Q(status__iexact='Paid')
        ).order_by('-created_at')

        accepted_orders = seller_orders.filter(
            status__iexact='Accepted'
        ).order_by('-created_at')

        completed_orders = seller_orders.filter(
            status__iexact='Completed'
        ).order_by('-updated_at')

        # Extra stats for the dashboard cards
        total_stocks = ProductVariant.objects.filter(
            product__seller=user
        ).aggregate(total=Sum('stocks'))['total'] or 0

        total_orders = seller_orders.count()

        total_income = completed_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        context.update({
            'approved_count': counts['approved'],
            'pending_count': counts['pending'],
            'rejected_count': counts['rejected'],

            'incoming_orders': incoming_orders,
            'accepted_orders': accepted_orders,
            'completed_orders': completed_orders,

            'total_stocks': total_stocks,
            'total_orders': total_orders,
            'total_income': total_income,
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