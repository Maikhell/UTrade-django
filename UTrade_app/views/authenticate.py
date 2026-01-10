from django.shortcuts import redirect, render

def user_login(request):
    next_url = request.GET.get('products.show')