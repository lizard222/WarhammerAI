"""Render UML views with the installed Graphviz; sources remain editable."""
import subprocess
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/uml'
COMMON = 'graph [fontname="Times New Roman", fontsize=18, bgcolor="white", pad="0.3"]; node [fontname="Times New Roman", fontsize=15, shape=box, style="rounded", margin="0.16,0.10"]; edge [fontname="Times New Roman", fontsize=12];'
DIAGRAMS = {
    'components': '''digraph G { rankdir=LR;
    web [label="«component»\nВеб-клиент\nHTML / CSS / JavaScript"];
    gui [label="«component»\nНастольный клиент\nPython / Tkinter"];
    api [label="«component»\nСервис магазина\nDjango REST Framework"];
    db [shape=cylinder, label="«database»\nSQLite"];
    cloud [label="«component»\nСервис рекомендаций\nCloudflare Worker"];
    ai [label="«external service»\nWorkers AI\nLlama 3.3 70B"];
    web -> api [label="REST / JSON\nToken"];
    gui -> api [label="REST / JSON\nToken"];
    api -> db [label="Django ORM"];
    api -> cloud [label="HTTPS / JSON\nBearer service key"];
    cloud -> ai [label="AI binding\nenv.AI.run()"];
    }''',
    'use_cases': '''digraph G { rankdir=LR;
    buyer [label="«actor»\nПокупатель", style=""];
    admin [label="«actor»\nАдминистратор", style=""];
    model [label="«actor»\nWorkers AI", style=""];
    subgraph cluster_system { label="Warhammer AI Store"; fontname="Times New Roman"; fontsize=19;
      node [shape=ellipse];
      catalog [label="Просмотреть и\nотфильтровать каталог"];
      login [label="Войти в аккаунт"];
      recommend [label="Получить подбор\nтоваров по пожеланиям"];
      cart [label="Изменить корзину"];
      order [label="Оформить заказ"];
      history [label="Просмотреть\nсвои заказы"];
      manage [label="Управлять каталогом\nи остатками"];
    }
    buyer -> catalog; buyer -> login; buyer -> recommend; buyer -> cart; buyer -> order; buyer -> history;
    admin -> manage; admin -> login;
    recommend -> model [dir=none];
    }''',
    'classes': '''digraph G { rankdir=LR; node [shape=record, style=""];
    User [label="{User (Django)|id: int\\lusername: str\\lis_staff: bool\\l}"];
    Faction [label="{Faction|name: str\\ldescription: str\\l}"];
    Product [label="{Product|name: str\\lprice: Decimal\\lstock: int\\ltags: str\\lbeginner_friendly: bool\\l|get_discounted_price(): Decimal\\l}"];
    Cart [label="{Cart|created_at: datetime\\l}"];
    CartItem [label="{CartItem|quantity: int\\l|total_price(): Decimal\\l}"];
    Order [label="{Order|total_price: Decimal\\lstatus: str\\lcreated_at: datetime\\l}"];
    OrderItem [label="{OrderItem|product_name: str\\lunit_price: Decimal\\lquantity: int\\l|total_price(): Decimal\\l}"];
    User -> Cart [dir=none, taillabel="1", headlabel="0..1"];
    User -> Order [dir=none, taillabel="1", headlabel="0..*"];
    Faction -> Product [dir=none, taillabel="0..1", headlabel="0..*"];
    Cart -> CartItem [dir=both, arrowtail=diamond, arrowhead=none, taillabel="1", headlabel="0..*"];
    Product -> CartItem [dir=none, taillabel="1", headlabel="0..*"];
    Order -> OrderItem [dir=both, arrowtail=diamond, arrowhead=none, taillabel="1", headlabel="1..*"];
    Product -> OrderItem [dir=none, taillabel="0..1", headlabel="0..*"];
    }''',
    'deployment': '''digraph G { rankdir=LR;
    subgraph cluster_pc { label="«device» Компьютер пользователя"; fontname="Times New Roman"; fontsize=18;
      browser [label="«executionEnvironment»\nВеб-браузер"];
      desktop [label="«executionEnvironment»\nPython + Tkinter"];
    }
    subgraph cluster_server { label="«node» Сервер магазина (локальная сеть)"; fontname="Times New Roman"; fontsize=18;
      django [label="«artifact»\nDjango application\nport 8000"];
      sqlite [shape=cylinder, label="«artifact»\ndb.sqlite3"];
      media [label="«artifact»\nЛокальные изображения"];
    }
    subgraph cluster_cf { label="«node» Cloudflare"; fontname="Times New Roman"; fontsize=18;
      worker [label="«executionEnvironment»\nWorkers\nworker.mjs"];
      ai [label="«executionEnvironment»\nWorkers AI / GPU\nLlama 3.3 70B"];
    }
    browser -> django [label="HTTP / JSON"];
    desktop -> django [label="HTTP / JSON"];
    django -> sqlite [dir=none]; django -> media [dir=none];
    django -> worker [label="HTTPS / JSON"];
    worker -> ai [label="AI binding"];
    }''',
}


def sequence():
    from PIL import Image, ImageDraw, ImageFont
    width, height = 1600, 1100
    im = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype('C:/Windows/Fonts/times.ttf', 24)
    small = ImageFont.truetype('C:/Windows/Fonts/times.ttf', 22)
    xs = [150, 550, 1000, 1430]
    names = ['Веб / GUI-клиент', 'Django API', 'Cloudflare Worker', 'Workers AI']
    for x, name in zip(xs, names):
        draw.rectangle((x-135, 40, x+135, 105), outline='black', width=2)
        draw.text((x, 72), name, font=font, fill='black', anchor='mm')
        for y in range(105, 1050, 18):
            draw.line((x, y, x, y+9), fill='#777777', width=1)
    messages = [(0,1,'1: POST /recommendations/ (пожелания, бюджет)'),
                (1,1,'2: Проверка входных данных, авторизации и кеша'),
                (1,1,'3: Отбор доступных товаров из БД'),
                (1,2,'4: POST /recommendations (кандидаты, Bearer key)'),
                (2,2,'5: Валидация запроса и подготовка промпта'),
                (2,3,'6: env.AI.run(model, messages, json_schema)'),
                (3,2,'7: Структурированный ответ модели'),
                (2,2,'8: Проверка IDs, количества и бюджета'),
                (2,1,'9: JSON: items, model'),
                (1,1,'10: Повторная проверка цен и остатков; кеш 5 мин'),
                (1,0,'11: HTTP 200: товары, объяснения, сумма'),
                (0,0,'12: Показ карточек и добавление в корзину')]
    y=155
    for a,b,text in messages:
        x1,x2=xs[a],xs[b]
        if a==b:
            draw.line((x1,y,x1+60,y,x1+60,y+28,x1,y+28),fill='black',width=2)
            draw.polygon([(x1,y+28),(x1+10,y+23),(x1+10,y+33)], fill='black')
            tx=x1+75
            if tx+600>width: tx=x1-400
            draw.text((tx,y+8),text,font=small,fill='black')
        else:
            draw.line((x1,y+28,x2,y+28),fill='black',width=2)
            d=1 if x2>x1 else -1
            draw.polygon([(x2,y+28),(x2-d*12,y+22),(x2-d*12,y+34)],fill='black')
            draw.text(((x1+x2)/2,y),text,font=small,fill='black',anchor='mm')
        y+=72
    im.save(OUT/'sequence.png')


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True, parents=True)
    dot = which('dot') or r'D:\VS\Graphviz\bin\dot.exe'
    for name, source in DIAGRAMS.items():
        if name in ['components', 'classes', 'deployment']:
            source = source.replace('rankdir=LR', 'rankdir=TB')
        source = source.replace('{', '{'+COMMON, 1)
        path = OUT / (name + '.dot')
        path.write_text(source, encoding='utf-8')
        subprocess.run([dot, '-Tpng', '-Gdpi=170', str(path), '-o', str(OUT/(name+'.png'))], check=True)
        subprocess.run([dot, '-Tsvg', str(path), '-o', str(OUT/(name+'.svg'))], check=True)
    sequence()
    (OUT/'sequence.puml').write_text('''@startuml
actor "Покупатель" as Buyer
participant "Веб / GUI-клиент" as Client
participant "Django API" as Django
database SQLite
participant "Cloudflare Worker" as Worker
participant "Workers AI" as AI
Buyer -> Client: Пожелания и бюджет
Client -> Django: POST /api/v1/recommendations/
Django -> Django: Авторизация, валидация, кеш
Django -> SQLite: Доступные товары и текущие цены
SQLite --> Django: Кандидаты
Django -> Worker: POST /recommendations, Bearer key
Worker -> Worker: Валидация; промпт и JSON Schema
Worker -> AI: env.AI.run(model, messages)
AI --> Worker: items: product_id, quantity, reason
Worker -> Worker: Проверка идентификаторов и бюджета
Worker --> Django: JSON: items, model
Django -> Django: Проверка цен и остатков; сумма; кеш
Django --> Client: HTTP 200: товары и объяснения
Client --> Buyer: Карточки рекомендованных товаров
@enduml
''', encoding='utf-8')
    print('UML diagrams generated:', len(DIAGRAMS)+1)
