from django.contrib import admin
from .models import Faction, Product, Cart, CartItem, Order, OrderItem


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_type', 'price', 'stock', 'beginner_friendly']
    list_filter = ['product_type', 'faction', 'beginner_friendly']
    search_fields = ['name', 'description', 'tags']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ['product', 'product_name', 'unit_price', 'quantity']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'total_price', 'status', 'created_at']
    readonly_fields = ['user', 'total_price', 'created_at']
    inlines = [OrderItemInline]


admin.site.register([Faction, Cart, CartItem])
admin.site.site_header = 'Warhammer AI · Управление магазином'
