import io
import json
from decimal import Decimal
from unittest.mock import patch
from urllib.error import URLError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APITestCase
from .models import Faction, Product, Cart, CartItem, Order, OrderItem


class StoreTests(APITestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user('buyer', password='TestPassword2026!')
        self.other = User.objects.create_user('other', password='TestPassword2026!')
        self.admin = User.objects.create_superuser('owner', 'owner@example.test', 'TestPassword2026!')
        self.faction = Faction.objects.create(name='Империум', description='Тест')
        self.product = Product.objects.create(name='Набор космодесанта', faction=self.faction,
            product_type='STARTER_SET', description='Для новичка', price='1000.00', stock=5, beginner_friendly=True)
        self.paint = Product.objects.create(name='Синяя краска', product_type='PAINT', description='Для покраски', price='100.00', stock=10)

    def auth(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def add(self, product=None, quantity=1):
        return self.client.post('/api/v1/cart/', {'product_id': (product or self.product).pk, 'quantity': quantity}, format='json')

    def test_public_catalog_and_discount(self):
        r = self.client.get('/api/v1/products/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)
        self.assertEqual(r.data[0]['discounted_price'], '900.00')

    def test_price_filter_uses_discount(self):
        r = self.client.get('/api/v1/products/?min_price=850&max_price=950')
        self.assertEqual([p['id'] for p in r.data], [self.product.pk])

    def test_filter_category_faction_and_search(self):
        r = self.client.get(f'/api/v1/products/?faction={self.faction.pk}&type=STARTER_SET&search=космодесанта')
        self.assertEqual(len(r.data), 1)

    def test_invalid_filters_return_400(self):
        for params in ['faction=no', 'type=UNKNOWN', 'max_price=NaN', 'min_price=-1', 'min_price=20&max_price=10', 'ordering=no']:
            with self.subTest(params=params):
                self.assertEqual(self.client.get('/api/v1/products/?' + params).status_code, 400)

    def test_catalog_writes_require_admin(self):
        self.auth()
        self.assertEqual(self.client.patch(f'/api/v1/products/{self.product.pk}/', {'price': '5.00'}, format='json').status_code, 403)
        self.auth(self.admin)
        self.assertEqual(self.client.patch(f'/api/v1/products/{self.product.pk}/', {'price': '500.00'}, format='json').status_code, 200)

    def test_auth_required_for_private_endpoints(self):
        for path in ['cart/', 'orders/', 'auth/me/']:
            self.assertEqual(self.client.get('/api/v1/' + path).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/recommendations/', {}, format='json').status_code, 401)

    def test_login_and_logout_revoke_token(self):
        result = self.client.post('/api/v1/auth/login/', {'username': 'buyer', 'password': 'TestPassword2026!'}, format='json')
        self.assertEqual(result.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + result.data['token'])
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)

    def test_bad_login(self):
        self.assertEqual(self.client.post('/api/v1/auth/login/', {'username': 'buyer', 'password': 'wrong'}, format='json').status_code, 401)

    def test_cart_contains_items_and_correct_total(self):
        self.auth()
        self.assertEqual(self.add(quantity=2).status_code, 201)
        r = self.client.get('/api/v1/cart/')
        self.assertEqual(len(r.data['items']), 1)
        self.assertEqual(r.data['total_price'], '1800.00')
        self.assertEqual(r.data['total_quantity'], 2)

    def test_cart_merges_same_product(self):
        self.auth()
        self.add()
        self.add(quantity=2)
        self.assertEqual(CartItem.objects.count(), 1)
        self.assertEqual(CartItem.objects.get().quantity, 3)

    def test_quantity_validation_and_stock(self):
        self.auth()
        for quantity in [0, -1, 'abc', 6]:
            self.assertEqual(self.add(quantity=quantity).status_code, 400)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_cart_patch_and_delete(self):
        self.auth()
        self.add()
        item = CartItem.objects.get()
        path = f'/api/v1/cart/items/{item.pk}/'
        self.assertEqual(self.client.patch(path, {'quantity': 3}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(path, {'quantity': 9}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(path).status_code, 204)

    def test_other_user_cannot_change_cart(self):
        self.auth()
        self.add()
        item = CartItem.objects.get()
        self.auth(self.other)
        self.assertEqual(self.client.delete(f'/api/v1/cart/items/{item.pk}/').status_code, 404)

    def test_order_saves_price_snapshot_and_clears_cart(self):
        self.auth()
        self.add(quantity=2)
        self.add(self.paint, 1)
        r = self.client.post('/api/v1/orders/', {}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['total_price'], '1900.00')
        self.assertEqual(len(r.data['items']), 2)
        self.assertEqual(CartItem.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.product.price = Decimal('2000.00')
        self.product.name = 'Новое название'
        self.product.save()
        self.product.delete()
        snapshot = OrderItem.objects.get(product_name='Набор космодесанта')
        self.assertEqual(snapshot.unit_price, Decimal('900.00'))
        self.assertIsNone(snapshot.product)

    def test_failed_order_rolls_back_all_stock(self):
        self.auth()
        self.add()
        self.add(self.paint, 2)
        self.paint.stock = 1
        self.paint.save()
        self.assertEqual(self.client.post('/api/v1/orders/').status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(CartItem.objects.count(), 2)

    def test_empty_order_and_repeated_checkout(self):
        self.auth()
        self.assertEqual(self.client.post('/api/v1/orders/').status_code, 400)
        self.add()
        self.assertEqual(self.client.post('/api/v1/orders/').status_code, 201)
        self.assertEqual(self.client.post('/api/v1/orders/').status_code, 400)
        self.assertEqual(Order.objects.count(), 1)

    def test_order_is_private(self):
        self.auth()
        self.add()
        order_id = self.client.post('/api/v1/orders/').data['id']
        self.auth(self.other)
        self.assertEqual(self.client.get('/api/v1/orders/').data, [])
        self.assertEqual(self.client.get(f'/api/v1/orders/{order_id}/').status_code, 404)

    def test_seed_is_idempotent_and_does_not_reset_stock(self):
        call_command('seed_demo', stdout=io.StringIO())
        count = Product.objects.count()
        p = Product.objects.get(name='Ультрамарины')
        p.stock = 1
        p.save()
        call_command('seed_demo', stdout=io.StringIO())
        self.assertEqual(Product.objects.count(), count)
        p.refresh_from_db()
        self.assertEqual(p.stock, 1)

    def test_recommendations_input_validation(self):
        self.auth()
        self.assertEqual(self.client.post('/api/v1/recommendations/', {'preferences': 'a', 'budget': '-1'}, format='json').status_code, 400)

    def test_no_candidates_does_not_invoke_cloud(self):
        self.auth()
        with patch('store.services.urlopen') as remote:
            r = self.client.post('/api/v1/recommendations/', {'preferences': 'Хочу начать', 'budget': '1'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['items'], [])
        remote.assert_not_called()

    @override_settings(RECOMMENDATIONS_URL='https://worker.example.test', RECOMMENDATIONS_API_KEY='test')
    def test_recommendations_reject_unknown_duplicates_and_overspend(self):
        self.auth()
        output = {'model': 'test-model', 'items': [
            {'product_id': 99999, 'quantity': 1, 'reason': 'Выдуманный товар'},
            {'product_id': self.product.pk, 'quantity': 9, 'reason': 'Больше остатка'},
            {'product_id': self.product.pk, 'quantity': 1, 'reason': 'Для новичка'},
            {'product_id': self.product.pk, 'quantity': 1, 'reason': 'Дубликат'},
            {'product_id': self.paint.pk, 'quantity': 2, 'reason': 'Не укладывается в оставшийся бюджет'}]}
        with patch('store.services.urlopen') as remote:
            remote.return_value.__enter__.return_value.read.return_value = json.dumps(output).encode()
            r = self.client.post('/api/v1/recommendations/', {'preferences': 'Хочу начать', 'budget': '950'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['items']), 1)
        self.assertEqual(r.data['total_price'], '900.00')

    @override_settings(RECOMMENDATIONS_URL='https://worker.example.test', RECOMMENDATIONS_API_KEY='test')
    def test_recommendation_cache_and_current_stock(self):
        self.auth()
        output = {'model': 'test', 'items': [{'product_id': self.paint.pk, 'quantity': 1, 'reason': 'Для покраски'}]}
        payload = {'preferences': 'Нужны краски', 'budget': '500'}
        with patch('store.services.urlopen') as remote:
            remote.return_value.__enter__.return_value.read.return_value = json.dumps(output).encode()
            first = self.client.post('/api/v1/recommendations/', payload, format='json')
            second = self.client.post('/api/v1/recommendations/', payload, format='json')
            self.assertEqual(remote.call_count, 1)
        self.assertFalse(first.data['cached'])
        self.assertTrue(second.data['cached'])
        self.paint.stock = 0
        self.paint.save()
        with patch('store.services.urlopen') as remote:
            r = self.client.post('/api/v1/recommendations/', payload, format='json')
        self.assertEqual(r.data['items'], [])
        remote.assert_not_called()

    @override_settings(RECOMMENDATIONS_URL='https://worker.example.test', RECOMMENDATIONS_API_KEY='test')
    def test_cloud_failure_and_malformed_response(self):
        self.auth()
        payload = {'preferences': 'Хочу начать', 'budget': '1000'}
        with patch('store.services.urlopen', side_effect=URLError('offline')):
            self.assertEqual(self.client.post('/api/v1/recommendations/', payload, format='json').status_code, 503)
        with patch('store.services.urlopen') as remote:
            remote.return_value.__enter__.return_value.read.return_value = b'not json'
            self.assertEqual(self.client.post('/api/v1/recommendations/', payload, format='json').status_code, 503)

    def test_recommendation_throttle(self):
        self.auth()
        payload = {'preferences': 'Хочу начать', 'budget': '1'}
        for _ in range(10):
            self.assertEqual(self.client.post('/api/v1/recommendations/', payload, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/recommendations/', payload, format='json').status_code, 429)

    def test_web_page_and_schema(self):
        self.assertContains(self.client.get('/'), 'WARHAMMER')
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
