from django.views.generic import ListView, CreateView, DeleteView, DetailView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model


User = get_user_model()
class AdminDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'UTrade_app/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context ['users'] = User.objects.all().order_by('-date_joined')
        return context
    