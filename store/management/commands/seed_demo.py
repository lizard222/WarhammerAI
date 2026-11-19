import json
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from store.models import Faction, Product

# All prices, descriptions and stock levels are fictional educational data.
CATALOG = [
    ('Ультрамарины', 'Империум', 'MINIATURE', '5000', 8, 'ultramarines.jpg', False,
     'Отряд космодесанта в синих доспехах. Подойдёт для расширения армии Империума и отработки аккуратной покраски брони.', 'космодесант синий ультрамарины армия'),
    ('Гвардия Ворона', 'Империум', 'STARTER_SET', '2500', 6, 'ravenguards.webp', True,
     'Небольшой стартовый набор для любителей скрытного космодесанта. Удобный первый проект для сборки и покраски чёрных доспехов.', 'космодесант чёрный новичок старт'),
    ('Гвардия Смерти', 'Хаос', 'STARTER_SET', '10000', 0, 'deathguards.jpg', False,
     'Набор воинов Хаоса с множеством фактур и деталей. Подойдёт опытному коллекционеру для экспериментов с эффектами старения.', 'хаос нургл опытный зелёный'),
    ('Космодесант: отряд Интерцессоров', 'Империум', 'MINIATURE', '4200', 10, 'intercessors.jpg', True,
     'Универсальный отряд пехоты космодесанта. Подходит для знакомства со сборкой миниатюр и создания основы коллекции Империума.', 'космодесант пехота новичок универсальный'),
    ('Орки: отряд Бойзов', 'Орки', 'MINIATURE', '3300', 7, 'orks.jpg', True,
     'Бойцы для тех, кому нравятся орки, динамичные позы и яркая покраска. Хорошая отправная точка для зелёной армии.', 'орки зелёный ближний бой новичок'),
    ('Аэльдари: Стражи', 'Аэльдари', 'MINIATURE', '3800', 5, 'aeldari.jpg', False,
     'Изящная пехота Аэльдари с тонкими деталями. Подойдёт коллекционеру, которому интересны точная покраска и эстетика этой фракции.', 'аэльдари эльдары пехота точная покраска'),
    ('Некроны: Воины', 'Некроны', 'MINIATURE', '3600', 8, 'necrons.jpg', True,
     'Механические воины для начала армии некронов. Металлические поверхности позволяют освоить базовые приёмы покраски и проливки.', 'некроны металл роботы новичок'),
    ('Warhammer 40,000: стартовый набор', 'Империум', 'STARTER_SET', '6000', 4, 'starter.jpg', True,
     'Стартовый набор для знакомства с настольными сражениями и сборкой миниатюр. Рекомендуется новичкам, которым нужен основной набор для начала хобби.', 'новичок старт космодесант знакомство игра'),
    ('Warhammer 40,000: вводный набор', 'Империум', 'STARTER_SET', '3500', 9, 'introductory.jpg', True,
     'Компактное знакомство со вселенной Warhammer. Подойдёт для первого опыта сборки, покраски и учебной игры без большого бюджета.', 'новичок бюджетный старт покраска космодесант'),
    ('Citadel: краски и инструменты', None, 'PAINT', '2200', 12, 'paints.jpg', True,
     'Базовый комплект для начала покраски миниатюр: несколько основных цветов и инструменты. Полезное дополнение к первому отряду любой фракции.', 'краски инструменты новичок покраска набор'),
    ('Citadel Base: Macragge Blue', None, 'PAINT', '450', 20, 'blue.jpg', True,
     'Синяя базовая акриловая краска для миниатюр. Подойдёт для доспехов ультрамаринов и других синих элементов. Требуется кисть.', 'краска синий ультрамарины космодесант покраска'),
    ('Citadel Base: Abaddon Black', None, 'PAINT', '450', 18, 'black.jpg', True,
     'Чёрная базовая краска для доспехов, оружия и деталей. Универсальный цвет для большинства схем покраски и Гвардии Ворона.', 'краска чёрный гвардия ворона покраска'),
    ('Warhammer Colour: базовая кисть', None, 'ACCESSORY', '650', 15, 'brush.jpg', True,
     'Кисть для нанесения базовых цветов на миниатюры. Подходит начинающим художникам и для повседневной работы с акриловыми красками.', 'кисть покраска новичок инструменты'),
    ('Кубики Warhammer: Космодесант', 'Империум', 'ACCESSORY', '850', 11, 'dice.jpg', True,
     'Набор игровых кубиков в тематике космодесанта. Дополнение к армии для настольных сражений; для покраски миниатюр не требуется.', 'кубики игра космодесант аксессуары'),
    ('Warhammer 40,000: книга правил', None, 'BOOK', '1900', 6, 'book.jpg', True,
     'Книга для знакомства с основами настольных сражений и устройством игры. Подойдёт тем, кто хочет перейти от коллекционирования к первым партиям.', 'правила книга новичок игра обучение'),
]


class Command(BaseCommand):
    help = 'Create 15 educational products and demo users; repeated runs do not duplicate or reset existing stock/passwords.'

    def add_arguments(self, parser):
        parser.add_argument('--reset-stock', action='store_true', help='Restore only the demonstration stock levels.')

    @transaction.atomic
    def handle(self, *args, **options):
        logos = {'Империум': 'loyal.jpg', 'Хаос': 'chaos.jpg', 'Орки': 'orks.jpg', 'Аэльдари': 'aeldari.jpg'}
        factions = {}
        for name in ['Империум', 'Хаос', 'Орки', 'Аэльдари', 'Некроны']:
            factions[name], _ = Faction.objects.get_or_create(name=name, defaults={'description': 'Товары фракции «' + name + '».',
                                                                                 'logo': 'factions/' + logos[name] if name in logos else ''})
        source_path = settings.BASE_DIR / 'docs/image_sources.json'
        sources = json.loads(source_path.read_text(encoding='utf-8')) if source_path.exists() else {}
        created = 0
        for name, faction, kind, price, stock, image, beginner, description, tags in CATALOG:
            source = sources.get(Path(image).stem, {}).get('page', '')
            defaults = {'faction': factions.get(faction), 'product_type': kind, 'price': Decimal(price), 'stock': stock,
                        'image': 'products/' + image, 'beginner_friendly': beginner, 'description': description, 'tags': tags, 'image_source': source}
            product, was_created = Product.objects.get_or_create(name=name, defaults=defaults)
            created += int(was_created)
            if not was_created:
                # Refresh educational text/images, but preserve stock and prices after real use.
                for key in ['description', 'tags', 'image', 'image_source', 'beginner_friendly']:
                    setattr(product, key, defaults[key])
                if options['reset_stock']:
                    product.stock = stock
                product.save()
        User = get_user_model()
        for username, password, staff in [('demo', 'WarhammerDemo2026!', False), ('admin', 'WarhammerAdmin2026!', True)]:
            user, new = User.objects.get_or_create(username=username, defaults={'is_staff': staff, 'is_superuser': staff})
            if new:
                user.set_password(password)
                user.save()
        self.stdout.write(self.style.SUCCESS(f'Products: {Product.objects.count()}; added: {created}. Demo users: demo, admin.'))
