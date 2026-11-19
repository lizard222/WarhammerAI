from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views as api

router = DefaultRouter()
router.register('factions', api.FactionViewSet)
router.register('products', api.ProductViewSet)
urlpatterns = [path('', include(router.urls)),
    path('auth/login/', api.LoginAPIView.as_view()), path('auth/logout/', api.LogoutAPIView.as_view()),
    path('auth/me/', api.MeAPIView.as_view()), path('cart/', api.CartAPIView.as_view()),
    path('cart/items/<int:item_id>/', api.CartItemAPIView.as_view()),
    path('orders/', api.OrderListAPIView.as_view()), path('orders/<int:order_id>/', api.OrderDetailAPIView.as_view()),
    path('recommendations/', api.RecommendationAPIView.as_view())]
