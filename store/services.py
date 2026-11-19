"""Business rules shared by both clients."""
import hashlib
import json
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import APIException, ValidationError
from .models import Cart, Order, OrderItem, Product


class CloudUnavailable(APIException):
    status_code = 503
    default_detail = 'Сервис подбора временно недоступен. Попробуйте позже.'


@transaction.atomic
def checkout(user):
    # Conditional updates also protect stock on SQLite, which has no row locks.
    cart, _ = Cart.objects.get_or_create(user=user)
    rows = list(cart.items.select_for_update().select_related('product'))
    if not rows:
        raise ValidationError({'detail': 'Корзина пуста.'})
    total, snapshots = Decimal('0.00'), []
    for row in rows:
        product = Product.objects.select_for_update().get(pk=row.product_id)
        changed = Product.objects.filter(pk=product.pk, stock__gte=row.quantity).update(stock=F('stock') - row.quantity)
        if not changed:
            raise ValidationError({'detail': f'Недостаточно товара «{product.name}».'})
        price = product.get_discounted_price()
        total += price * row.quantity
        snapshots.append((product, row.quantity, price))
    order = Order.objects.create(user=user, total_price=total)
    OrderItem.objects.bulk_create([OrderItem(order=order, product=p, product_name=p.name, quantity=q, unit_price=price)
                                   for p, q, price in snapshots])
    cart.items.all().delete()
    return order


def recommend(data):
    candidates = Product.objects.select_related('faction').filter(stock__gt=0)
    if data.get('faction'):
        candidates = candidates.filter(faction_id=data['faction'])
    if data.get('product_type'):
        candidates = candidates.filter(product_type=data['product_type'])
    products = [p for p in candidates.order_by('id') if p.get_discounted_price() <= data['budget']][:50]
    if not products:
        return {'items': [], 'total_price': '0.00', 'budget': str(data['budget']),
                'explanation': 'По указанным ограничениям доступных товаров нет. Увеличьте бюджет или измените фильтры.',
                'model': 'none', 'cached': False}
    if not settings.RECOMMENDATIONS_URL or not settings.RECOMMENDATIONS_API_KEY:
        raise CloudUnavailable('Облачный сервис ещё не настроен. Заполните RECOMMENDATIONS_URL и RECOMMENDATIONS_API_KEY.')
    payload = {'preferences': data['preferences'], 'budget': str(data['budget']), 'max_items': data['max_items'],
               'products': [{'id': p.pk, 'name': p.name, 'faction': p.faction.name if p.faction else 'Общие товары',
                             'category': p.get_product_type_display(), 'description': p.description[:500],
                             'price': str(p.get_discounted_price()), 'stock': p.stock,
                             'tags': p.tags, 'beginner_friendly': p.beginner_friendly} for p in products]}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
    key = 'recommend:' + hashlib.sha256(encoded).hexdigest()
    result = cache.get(key)
    cached = result is not None
    if result is None:
        request = Request(settings.RECOMMENDATIONS_URL.rstrip('/') + '/recommendations', data=encoded,
                          headers={'Authorization': 'Bearer ' + settings.RECOMMENDATIONS_API_KEY,
                                   'Content-Type': 'application/json', 'User-Agent': 'WarhammerCoursework/1.0'})
        try:
            with urlopen(request, timeout=settings.RECOMMENDATIONS_TIMEOUT) as response:
                raw = response.read(100001)
                if len(raw) > 100000:
                    raise ValueError('Response too large')
                result = json.loads(raw)
            if not isinstance(result, dict) or not isinstance(result.get('items'), list):
                raise ValueError('Invalid result')
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
            raise CloudUnavailable() from None
        cache.set(key, result, 300)
    current = {p.pk: p for p in Product.objects.select_related('faction').filter(pk__in=[p.pk for p in products])}
    items, seen, total = [], set(), Decimal('0.00')
    for proposal in result['items'][:10]:
        if not isinstance(proposal, dict):
            continue
        pid, quantity = proposal.get('product_id'), proposal.get('quantity', 1)
        if type(pid) is not int or type(quantity) is not int or pid not in current or pid in seen or quantity < 1:
            continue
        product = current[pid]
        if quantity > product.stock:
            continue
        cost = product.get_discounted_price() * quantity
        if total + cost > data['budget']:
            continue
        reason = proposal.get('reason', '')
        if not isinstance(reason, str):
            continue
        items.append({'product': product, 'quantity': quantity, 'reason': reason[:700], 'total_price': cost})
        seen.add(pid)
        total += cost
        if len(items) >= data['max_items']:
            break
    explanation = 'Подбор проверен по текущим ценам и наличию. Все выбранные товары вместе укладываются в бюджет.' if items else 'Модель не предложила подходящий набор. Уточните пожелания или измените ограничения.'
    return {'items': items, 'total_price': total, 'budget': data['budget'], 'explanation': explanation,
            'model': str(result.get('model', 'cloudflare'))[:120], 'cached': cached}
