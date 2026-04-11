import json
import logging
from django.shortcuts import render
from django.views.generic import ListView,TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from ..models import Product, Services, User, ProhibitedWord, Category,MeetupLocation
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404

User = get_user_model()
class AdminDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'UTrade_app/admin/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user_stats = User.objects.aggregate(
            total_admin=Count('id', filter=Q(is_staff=True)),
            unverified=Count('id', filter=Q(status='unverified')),
            verified=Count('id', filter=Q(status='verified'))
        )
        
        all_products = Product.objects.all().select_related('seller', 'category').prefetch_related('variants').order_by('-created_at')
        
        context.update({
            'users': User.objects.all().order_by('-date_joined')[:10],
            'admin': user_stats['total_admin'],        
            'unverified': user_stats['unverified'],   
            'verified': user_stats['verified'],      
            'products': all_products[:10],
            'pending_products': [p for p in all_products if p.status == 'Pending'][:5],
        })
        return context
    
@staff_member_required
def update_item_status(request, item_id): # Renamed for clarity
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        item_type = data.get('item_type') 
        
        ModelClass = Product if item_type == 'product' else Services
        
        # Use get_object_or_404 for cleaner error handling
        item = get_object_or_404(ModelClass, id=item_id)
        
        item.status = new_status
        
        if hasattr(item, 'is_authorized'):
            item.is_authorized = (new_status == 'Approved')
            
        item.save()
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class AdminReviewListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'UTrade_app/admin/product_review_list.html'

    
    def get_queryset(self):
        return Product.objects.filter(status='Pending')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Fetch Pending Products
        context['pending_products'] = Product.objects.filter(status='Pending')\
            .select_related('seller', 'category')\
            .prefetch_related('variants', 'images')\
            .order_by('created_at')
            
        # Fetch Pending Services
        context['pending_services'] = Services.objects.filter(status='Pending')\
            .select_related('seller', 'category')\
            .prefetch_related('images')\
            .order_by('created_at')
        #Retrieve the pending users dapat
        context['pending_users'] = User.objects.filter(status='Pending').only(
            'first_name', 'last_name', 'course', 'section', 'student_no', 'cor_file'
        ).order_by('date_joined')
        return context

    def test_func(self):
        return self.request.user.is_staff

logger = logging.getLogger(__name__)

class UpdateStatusView(View):
    def post(self, request, item_type, item_id):
        try:
            data = json.loads(request.body)
            new_status = data.get('status')

            item_type = item_type.lower().strip()

            if item_type == 'user':
                target_user = get_object_or_404(User, id=item_id)
                if new_status == 'Approved':
                    target_user.status = 'verified'
                    target_user.is_active = True
                else:
                    target_user.status = 'Rejected'
                target_user.save()
                return JsonResponse({'status': 'success'})

            elif item_type == 'product':
                target_product = get_object_or_404(Product, id=item_id)
                target_product.status = new_status
                target_product.save()
                return JsonResponse({'status': 'success'})

            elif item_type == 'service':
                target_service = get_object_or_404(Services, id=item_id)
                target_service.status = new_status
                target_service.save()
                return JsonResponse({'status': 'success'})

            return JsonResponse({'status': 'error', 'message': 'Invalid item type'}, status=400)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
def get_prohibited_words(request):
    words = list(ProhibitedWord.objects.values_list('word', flat=True))
    return JsonResponse({'prohibited_words': words})

def security_admin(request):
    context = {
        'prohibited_words': ProhibitedWord.objects.all().order_by('-created_at'),
        'categories': Category.objects.all().order_by('name'),
        'meetups': MeetupLocation.objects.all().order_by('name'), # Ensure this is here!    
}
    return render(request, 'UTrade_app/admin/admin_security.html', context)

@require_POST
def add_bad_word(request):
    word_text = request.POST.get('word', '').strip().lower()
    if word_text:
        word_obj, created = ProhibitedWord.objects.get_or_create(word=word_text)
        if created:
            return JsonResponse({
                'status': 'success', 
                'word': word_obj.word, 
                'id': word_obj.id
            })
        return JsonResponse({'status': 'error', 'message': 'Word already exists.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid input.'})

@require_POST
def delete_bad_word(request, word_id):
    try:
        word = ProhibitedWord.objects.get(id=word_id)
        word.delete()
        return JsonResponse({'status': 'success'})
    except ProhibitedWord.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Word not found.'})
    
@require_POST
def add_category(request):
    name = request.POST.get('name', '').strip()
    if name:
        # get_or_create prevents duplicates
        category, created = Category.objects.get_or_create(name=name)
        if created:
            return JsonResponse({'status': 'success', 'name': category.name, 'id': category.id})
        return JsonResponse({'status': 'error', 'message': 'Category already exists.'})
    return JsonResponse({'status': 'error', 'message': 'Name cannot be empty.'})

@require_POST
def delete_category(request, cat_id):
    try:
        category = Category.objects.get(id=cat_id)
        category.delete()
        return JsonResponse({'status': 'success'})
    except Category.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Category not found.'})
    
@require_POST
@login_required # Ensure only logged-in users/admins can add spots
def add_meetup(request):
    # Change 'location' to match what your JS formData.append uses
    location_name = request.POST.get('location', '').strip() 
    
    if location_name:
        # Check if it already exists (case-insensitive)
        if MeetupLocation.objects.filter(name__iexact=location_name).exists():
            return JsonResponse({'status': 'error', 'message': 'Location already exists.'}, status=400)

        # Create the new location with the audit trail
        location = MeetupLocation.objects.create(
            name=location_name,
            added_by=request.user  # This is the fix!
        )
        
        return JsonResponse({
            'status': 'success', 
            'location': location.name, 
            'id': location.id
        })
        
    return JsonResponse({'status': 'error', 'message': 'Location name is required.'}, status=400)
@require_POST
def delete_meetup(request, loc_id):
    try:
        location = MeetupLocation.objects.get(id=loc_id)
        location.delete()
        return JsonResponse({'status': 'success'})
    except MeetupLocation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Location not found.'})