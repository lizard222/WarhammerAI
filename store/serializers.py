from decimal import Decimal
from rest_framework import serializers
from .models import Faction, Product, Cart, CartItem, Order, OrderItem


class FactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faction
        fields = ['id', 'name', 'description', 'logo']


class ProductSerializer(serializers.ModelSerializer):
    faction = FactionSerializer(read_only=True)
    faction_id = serializers.PrimaryKeyRelatedField(queryset=Faction.objects.all(), source='faction', write_only=True, required=False, allow_null=True)
    discounted_price = serializers.DecimalField(source='get_discounted_price', max_digits=10, decimal_places=2, read_only=True)
    category_label = serializers.CharField(source='get_product_type_display', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'faction', 'faction_id', 'product_type', 'category_label', 'description',
                  'price', 'discounted_price', 'stock', 'image', 'tags', 'beginner_friendly', 'image_source']


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'total_price']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_price', 'total_quantity']

    def get_total_price(self, obj) -> str:
        return str(sum((i.total_price() for i in obj.items.all()), Decimal('0.00')))

    def get_total_quantity(self, obj) -> int:
        return sum(i.quantity for i in obj.items.all())


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(default=1, min_value=1, max_value=999)


class QuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class OrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['product', 'product_name', 'unit_price', 'quantity', 'total_price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'total_price', 'created_at', 'status', 'items']


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=200, trim_whitespace=False)


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    is_staff = serializers.BooleanField()


class LoginResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    user = UserSerializer()


class RecommendationRequestSerializer(serializers.Serializer):
    preferences = serializers.CharField(min_length=5, max_length=1200)
    budget = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1'), max_value=Decimal('1000000'))
    faction = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    product_type = serializers.ChoiceField(choices=Product.PRODUCT_TYPES, required=False)
    max_items = serializers.IntegerField(default=3, min_value=1, max_value=5)


class RecommendationItemSerializer(serializers.Serializer):
    product = ProductSerializer()
    quantity = serializers.IntegerField()
    reason = serializers.CharField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class RecommendationResponseSerializer(serializers.Serializer):
    items = RecommendationItemSerializer(many=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    explanation = serializers.CharField()
    model = serializers.CharField()
    cached = serializers.BooleanField()
