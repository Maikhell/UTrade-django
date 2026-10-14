from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
import io
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ..models import User, Product, Order,OrganizationPlatformLedger
from django.utils import timezone


def update_status_org(request, item_type, item_id):
    requested_status = request.GET.get('status')    
    if item_type == 'user' and requested_status == 'approved':
        final_status = 'verified'
    else:
        final_status = requested_status

    if item_type == 'user':
        obj = get_object_or_404(User, id=item_id)
        obj.status = final_status
        obj.save()
        messages.success(request, f"Student {obj.get_full_name()} is now {final_status}.")
        
    elif item_type == 'product':
        obj = get_object_or_404(Product, id=item_id)
        obj.status = requested_status
        obj.save()
        messages.success(request, f"Product '{obj.name}' has been {requested_status}.")
        
    return redirect('organization.panel')
