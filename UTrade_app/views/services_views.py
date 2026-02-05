from django.shortcuts import render,redirect
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView
from ..forms import ServiceForm
from ..models import Services, ServiceCategory

class ServiceCreateView(CreateView):
    form_class = ServiceForm
    template_name = 'Utrade_app/services/actions/addservices.html'
    success_url = reverse_lazy ('service.list')
    
    def get_context_data(self, **kwargs):
        context  = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.objects.all()
        
        return context
    def form_valid (self,form):
        self.object = form.save(commit=False)
        self.object.product_status = 'Approved'
        self.object.product_rating = 0.0
        self.object.owner = self.request.user
        self.object.save()
        return super().form_valid(form)
    
class ServiceListView(ListView):
    model = Services
    template_name = 'UTrade_app/services.html'
    context_object_name = 'service'

    def get_queryset(self):
        queryset = Services.objects.filter(status='Approved').order_by('-created_at')
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.objects.all()
        return context