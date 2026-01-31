from django.views.generic import ListView, CreateView, DeleteView, DetailView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model
from ..models import Products


User = get_user_model()
class AdminDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'UTrade_app/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context ['users'] = User.objects.all().order_by('-date_joined')
        context['admin'] = User.objects.filter(is_staff=True).count
        context ['unverified'] = User.objects.filter(status = 'unverified')
        context ['verified'] = User.objects.filter(status = 'verified')
        context ['products'] = Products.objects.all().order_by('-created_at')
        return context
    