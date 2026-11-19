from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Faction(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    logo = models.ImageField(upload_to='factions/', blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class Product(models.Model):
    PRODUCT_TYPES = [('MINIATURE', 'Миниатюры'), ('STARTER_SET', 'Стартовые наборы'),
                     ('PAINT', 'Краски'), ('ACCESSORY', 'Аксессуары'), ('BOOK', 'Книги правил')]
    name = models.CharField(max_length=200, unique=True)
    faction = models.ForeignKey(Faction, on_delete=models.SET_NULL, null=True, blank=True)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    stock = models.PositiveIntegerField(default=0)
    is_preorder = models.BooleanField(default=False)
    release_date = models.DateField(null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True)
    tags = models.CharField(max_length=300, blank=True)
    beginner_friendly = models.BooleanField(default=False)
    image_source = models.URLField(blank=True, max_length=500)

    class Meta:
        ordering = ['id']
        constraints = [models.CheckConstraint(condition=Q(price__gt=0), name='positive_product_price')]

    def get_discounted_price(self):
        factor = Decimal('0.9') if self.product_type == 'STARTER_SET' else Decimal('1')
        return (self.price * factor).quantize(Decimal('0.01'))

    def __str__(self):
        return self.name


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Корзина {self.user.username}'


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['cart', 'product'], name='unique_cart_product'),
                       models.CheckConstraint(condition=Q(quantity__gte=1), name='positive_cart_quantity')]

    def total_price(self):
        return self.product.get_discounted_price() * self.quantity


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='PROCESSING')

    class Meta:
        ordering = ['-created_at', '-id']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ['id']

    def total_price(self):
        return self.unit_price * self.quantity
