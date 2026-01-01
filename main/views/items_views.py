from django.shortcuts import render

def landing_page(request):
    return render(request, 'campusbuy_app/landingpage.html')