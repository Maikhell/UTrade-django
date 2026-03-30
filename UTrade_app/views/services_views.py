from django.shortcuts import render,redirect
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView
from ..forms import ServiceForm
from ..models import Services, ServiceCategory, ServicesImage
from django.contrib.auth.mixins import LoginRequiredMixin

class ServiceCreateView(LoginRequiredMixin,CreateView):
    form_class = ServiceForm
    template_name = 'Utrade_app/services/actions/addservices.html'
    success_url = reverse_lazy('service.list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # This matches the 'categories' name you used in your HTML loop
        context['categories'] = ServiceCategory.objects.all()
        return context
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        total_services = int(request.POST.get('total_services', 0))
        
        if total_services == 0:
            return super().post(request, *args, **kwargs)

        try:
            category_ids = [request.POST.get(f'serv_{i}_category') for i in range(total_services)]
            categories = {str(c.id): c for c in ServiceCategory.objects.filter(id__in=category_ids)}

            for i in range(total_services):
                # Manual Validation
                category = categories.get(request.POST.get(f'serv_{i}_category'))
                
                service = Services(
                    name=request.POST.get(f'serv_{i}_name'),
                    base_price=request.POST.get(f'serv_{i}_price'),
                    description=request.POST.get(f'serv_{i}_desc'),
                    turnaround_time=request.POST.get(f'serv_{i}_lead_time'), 
                    category=category,
                    seller=request.user,
                    status='Pending'
                )
                
                # Handle the primary image field on the Service model
                main_image = request.FILES.get(f'serv_{i}_image_0')
                if main_image:
                    service.image = main_image
                
                service.full_clean() # Triggers model validation
                service.save()

                # 2. Optimized Image Creation
                image_count = int(request.POST.get(f'serv_{i}_image_count', 0))
                gallery_images = []
                for j in range(image_count):
                    img_file = request.FILES.get(f'serv_{i}_image_{j}')
                    if img_file:
                        gallery_images.append(ServicesImage(service=service, image=img_file))
                
                # Bulk create gallery images for this specific service
                ServicesImage.objects.bulk_create(gallery_images)

            return JsonResponse({'status': 'success'})
        
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
class ServiceListView(ListView):
    model = Services
    template_name = 'UTrade_app/services.html'
    context_object_name = 'services'

    def get_queryset(self):
        # We want to show 'Approved' services to buyers, but 'Pending' for the admin
        # I'll stick to 'Pending' as per your code, but usually, this is 'Approved'
        queryset = Services.objects.filter(status='Pending').select_related('category')
        
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add categories so the filter dropdown works
        context['categories'] = ServiceCategory.objects.all()
        return context