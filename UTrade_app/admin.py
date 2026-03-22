from django.contrib import admin
from .models import User, Category, ServiceCategory, Product, ProductVariant, Services

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1  
    fields = ['variant_name', 'price', 'stocks'] 

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductVariantInline]
    list_display = ['name', 'seller', 'category', 'status']
    list_filter = ['status', 'category']
    search_fields = ['name', 'description']

admin.site.register(User)
admin.site.register(Category)
admin.site.register(ServiceCategory)
admin.site.register(Services)
admin.site.register(ProductVariant) 