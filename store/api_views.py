from decimal import Decimal, InvalidOperation
from django.contrib.auth import authenticate
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import F, Q, Case, When, DecimalField, Value
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import permissions, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from .models import Faction, Product, Cart, CartItem, Order
from .serializers import (FactionSerializer, ProductSerializer, CartSerializer, CartItemSerializer,
    AddToCartSerializer, QuantitySerializer, OrderSerializer, LoginSerializer, LoginResponseSerializer,
    UserSerializer, RecommendationRequestSerializer, RecommendationResponseSerializer)
from .services import checkout, recommend


class AdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or bool(request.user and request.user.is_staff)


class FactionViewSet(viewsets.ModelViewSet):
    queryset = Faction.objects.all()
    serializer_class = FactionSerializer
    permission_classes = [AdminOrReadOnly]


@extend_schema(parameters=[OpenApiParameter('search', str), OpenApiParameter('faction', int),
    OpenApiParameter('type', str), OpenApiParameter('min_price', str), OpenApiParameter('max_price', str),
    OpenApiParameter('in_stock', bool), OpenApiParameter('ordering', str)])
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('faction').all()
    serializer_class = ProductSerializer
    permission_classes = [AdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get('faction'):
            try:
                faction = int(params['faction'])
                if faction < 1: raise ValueError
            except ValueError:
                raise ValidationError({'faction': 'Укажите положительный идентификатор.'})
            qs = qs.filter(faction_id=faction)
        if params.get('type'):
            if params['type'] not in dict(Product.PRODUCT_TYPES):
                raise ValidationError({'type': 'Неизвестная категория.'})
            qs = qs.filter(product_type=params['type'])
        if params.get('search'):
            text = params['search'][:200]
            qs = qs.filter(Q(name__icontains=text) | Q(description__icontains=text) | Q(tags__icontains=text))
        qs = qs.annotate(effective_price=Case(When(product_type='STARTER_SET', then=F('price') * Value(Decimal('0.9'))),
                                             default=F('price'), output_field=DecimalField(max_digits=12, decimal_places=2)))
        prices = {}
        for key, lookup in [('min_price', 'effective_price__gte'), ('max_price', 'effective_price__lte')]:
            if params.get(key):
                try:
                    value = Decimal(params[key])
                    if not value.is_finite() or value < 0 or value > 1000000: raise InvalidOperation
                except (InvalidOperation, ValueError):
                    raise ValidationError({key: 'Укажите цену от 0 до 1000000.'})
                prices[key] = value
                qs = qs.filter(**{lookup: value})
        if prices.get('min_price', 0) > prices.get('max_price', 1000000):
            raise ValidationError({'min_price': 'Минимальная цена больше максимальной.'})
        if params.get('in_stock') in ['true', '1']:
            qs = qs.filter(stock__gt=0)
        order_map = {'id': 'id', 'price': 'effective_price', '-price': '-effective_price', 'name': 'name'}
        ordering = params.get('ordering', 'id')
        if ordering not in order_map:
            raise ValidationError({'ordering': 'Доступны id, price, -price, name.'})
        return qs.order_by(order_map[ordering], 'id')


class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @extend_schema(request=LoginSerializer, responses={200: LoginResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request=request, **serializer.validated_data)
        if user is None:
            return Response({'detail': 'Неверное имя пользователя или пароль.'}, status=401)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': UserSerializer(user).data})


class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)


class MeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class CartAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=CartSerializer)
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart, context={'request': request}).data)

    @extend_schema(request=AddToCartSerializer, responses={201: CartItemSerializer})
    @transaction.atomic
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, pk=serializer.validated_data['product_id'])
        amount = serializer.validated_data['quantity']
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item = cart.items.select_for_update().filter(product=product).first()
        wanted = amount + (item.quantity if item else 0)
        if wanted > product.stock or wanted > 999:
            raise ValidationError({'quantity': 'Количество превышает доступный остаток.'})
        if item:
            item.quantity = wanted
            item.save(update_fields=['quantity'])
        else:
            item = CartItem.objects.create(cart=cart, product=product, quantity=amount)
        return Response(CartItemSerializer(item, context={'request': request}).data, status=201)


class CartItemAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=QuantitySerializer, responses=CartItemSerializer)
    def patch(self, request, item_id):
        item = get_object_or_404(CartItem.objects.select_related('product'), pk=item_id, cart__user=request.user)
        serializer = QuantitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wanted = serializer.validated_data['quantity']
        if wanted > item.product.stock:
            raise ValidationError({'quantity': 'Количество превышает доступный остаток.'})
        item.quantity = wanted
        item.save(update_fields=['quantity'])
        return Response(CartItemSerializer(item, context={'request': request}).data)

    @extend_schema(responses={204: None})
    def delete(self, request, item_id):
        get_object_or_404(CartItem, pk=item_id, cart__user=request.user).delete()
        return Response(status=204)


class OrderListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=OrderSerializer(many=True))
    def get(self, request):
        return Response(OrderSerializer(Order.objects.filter(user=request.user).prefetch_related('items'), many=True).data)

    @extend_schema(request=None, responses={201: OrderSerializer})
    def post(self, request):
        return Response(OrderSerializer(checkout(request.user)).data, status=201)


class OrderDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=OrderSerializer)
    def get(self, request, order_id):
        return Response(OrderSerializer(get_object_or_404(Order.objects.prefetch_related('items'), pk=order_id, user=request.user)).data)


class RecommendationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'recommendations'

    @extend_schema(request=RecommendationRequestSerializer, responses={200: RecommendationResponseSerializer})
    def post(self, request):
        serializer = RecommendationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = recommend(serializer.validated_data)
        return Response(RecommendationResponseSerializer(result, context={'request': request}).data)
