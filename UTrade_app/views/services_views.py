from django.shortcuts import render,redirect
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView
from ..forms import ServiceForm
from ..models import Services, ServiceCategory, ServicesImage

class ServiceCreateView(CreateView):
    form_class = ServiceForm
    template_name = 'Utrade_app/services/actions/addservices.html'
    success_url = reverse_lazy('service.list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        total_services = int(request.POST.get('total_services', 0))
        
        if total_services == 0:
            return super().post(request, *args, **kwargs)

        try:
            with transaction.atomic():
                for i in range(total_services):
                    category_id = request.POST.get(f'serv_{i}_category')
                    category = ServiceCategory.objects.get(id=category_id)
                    
                    service = Services.objects.create(
                        name=request.POST.get(f'serv_{i}_name'),
                        base_price=request.POST.get(f'serv_{i}_price'),
                        description=request.POST.get(f'serv_{i}_desc'),
                        turnaround_time=request.POST.get(f'serv_{i}_lead_time'), 
                        category=category,
                        seller=request.user,
                        status='Pending'
                    )
                    image_count = int(request.POST.get(f'serv_{i}_image_count', 0))
                    for j in range(image_count):
                        image_file = request.FILES.get(f'serv_{i}_image_{j}')
                        
                        if image_file:
                            if j == 0 and hasattr(service, 'image'):
                                service.image = image_file
                                service.save()
                            ServicesImage.objects.create(product=service, image=image_file)

            return JsonResponse({'status': 'success'})
        
        except Exception as e:
            print(f"Error saving services: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
class ServiceListView(ListView):
    model = Services
    template_name = 'UTrade_app/services.html'
    context_object_name = 'services'

    def get_queryset(self):
        queryset = Services.objects.filter(status='Pending').order_by('-created_at')
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.objects.all()
        return context