"""Create the editable report, reusing typography and page geometry of the supplied coursework."""
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'Результат'
ORIGINAL_REFERENCE = ROOT.parent / 'документы/ПЗ_Маттиев_САПР-1.1.docx'
REFERENCE = ORIGINAL_REFERENCE if ORIGINAL_REFERENCE.exists() else ROOT / 'docs/report_template.docx'
TITLE = 'Клиент-серверное приложение интернет-магазина Warhammer с облачным сервисом интеллектуального подбора товаров'
DISCIPLINE = 'Мобильные и сетевые архитектуры комплексных систем искусственного интеллекта'


def set_report_font(font_owner, size=14):
    """Remove theme overrides: Word otherwise replaces the explicitly named heading font."""
    font_owner.font.name = 'Times New Roman'
    font_owner.font.size = Pt(size)
    font_owner.font.bold = False
    font_owner.font.color.rgb = RGBColor(0, 0, 0)
    element = font_owner.element if hasattr(font_owner, 'element') else font_owner._r
    props = element.get_or_add_rPr()
    fonts = props.find(qn('w:rFonts'))
    if fonts is None:
        fonts = OxmlElement('w:rFonts')
        props.insert(0, fonts)
    for attr in list(fonts.attrib):
        if attr.lower().endswith('theme'):
            del fonts.attrib[attr]
    for attr in ['ascii', 'hAnsi', 'eastAsia', 'cs']:
        fonts.set(qn('w:' + attr), 'Times New Roman')
    for name, value in [('szCs', str(size * 2)), ('bCs', '0')]:
        node = props.find(qn('w:' + name))
        if node is None:
            node = OxmlElement('w:' + name)
            props.append(node)
        node.set(qn('w:val'), value)


def main():
    OUT.mkdir(exist_ok=True)
    reference = Document(REFERENCE)
    doc = Document()
    # Copy the original stylesheet rather than substitute a generic Word theme.
    styles = doc.styles.element
    for element in list(styles):
        styles.remove(element)
    for element in reference.styles.element:
        styles.append(deepcopy(element))
    section, sample = doc.sections[0], reference.sections[0]
    for attr in ['page_width', 'page_height', 'top_margin', 'bottom_margin', 'left_margin', 'right_margin', 'header_distance', 'footer_distance']:
        setattr(section, attr, getattr(sample, attr))
    section.different_first_page_header_footer = True
    for name in ['Normal', 'Heading 1', 'Heading 2', 'Heading 3']:
        style = doc.styles[name]
        set_report_font(style)
        linked = style.element.find(qn('w:link'))
        if linked is not None:
            linked_id = linked.get(qn('w:val'))
            for linked_style in doc.styles:
                if linked_style.style_id == linked_id:
                    set_report_font(linked_style)
                    break
        style.element.get_or_add_rPr().append(OxmlElement('w:lang'))
        style.element.rPr[-1].set(qn('w:val'), 'ru-RU')
    normal = doc.styles['Normal'].paragraph_format
    normal.line_spacing = 1.5
    normal.first_line_indent = Cm(1.25)
    normal.space_before = Pt(0)
    normal.space_after = Pt(0)
    normal.widow_control = True
    for name in ['Heading 1', 'Heading 2', 'Heading 3']:
        doc.styles[name].paragraph_format.first_line_indent = Cm(1.25)
        doc.styles[name].paragraph_format.keep_with_next = True
    for name, size in [('Report Code', 10), ('Report Table', 12), ('Report Caption', 14)]:
        if name not in doc.styles:
            doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        st = doc.styles[name]
        st.base_style = doc.styles['Normal']
        st.font.name = 'Consolas' if name == 'Report Code' else 'Times New Roman'
        st.font.size = Pt(size)
        st.paragraph_format.first_line_indent = Cm(0)
        st.paragraph_format.line_spacing = 1.0 if name != 'Report Caption' else 1.5
        st.paragraph_format.space_after = Pt(3)
    for name in ['toc 1', 'toc 2', 'TOC 1', 'TOC 2']:
        if name in doc.styles:
            set_report_font(doc.styles[name])
            doc.styles[name].paragraph_format.line_spacing = 1.5
            doc.styles[name].paragraph_format.space_after = Pt(0)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.paragraph_format.first_line_indent = Cm(0)
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    footer._p.append(fld)
    doc.core_properties.title = TITLE
    doc.core_properties.author = 'Маттиев Рустам Алимжонович'
    doc.core_properties.subject = DISCIPLINE
    doc.core_properties.keywords = 'САПР-2.1, контрольная работа, Django, Cloudflare Workers AI'

    def p(text='', align=None, style='Normal'):
        para = doc.add_paragraph(text, style)
        para.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.JUSTIFY
        return para

    def h(text, level=1):
        para = doc.add_paragraph(text, f'Heading {level}')
        para.paragraph_format.line_spacing = 1.5
        for run in para.runs:
            set_report_font(run)
        return para

    def center(text='', size=14, bold=False, after=0):
        para = p('', WD_ALIGN_PARAGRAPH.CENTER)
        para.paragraph_format.first_line_indent = Cm(0)
        para.paragraph_format.space_after = Pt(after)
        run = para.add_run(text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(size)
        run.bold = bold
        return para

    def code(text):
        for line in text.strip('\n').splitlines():
            para = p(line, WD_ALIGN_PARAGRAPH.LEFT, 'Report Code')
            para.paragraph_format.keep_with_next = False

    figures, tables = [0], [0]

    def fig(path, caption, width=16.5, maxheight=18):
        figures[0] += 1
        im = Image.open(ROOT / path)
        w, hh = im.size
        actual_width = min(width, maxheight * w / hh)
        para = p('', WD_ALIGN_PARAGRAPH.CENTER)
        para.paragraph_format.first_line_indent = Cm(0)
        para.paragraph_format.keep_with_next = True
        para.add_run().add_picture(str(ROOT / path), width=Cm(actual_width))
        para = p(f'Рисунок {figures[0]} – {caption}', WD_ALIGN_PARAGRAPH.CENTER, 'Report Caption')
        para.paragraph_format.keep_with_next = False
        para.paragraph_format.space_after = Pt(8)

    def table(title, headers, rows, widths=None):
        tables[0] += 1
        cap = p(f'Таблица {tables[0]} – {title}', WD_ALIGN_PARAGRAPH.LEFT)
        cap.paragraph_format.first_line_indent = Cm(0)
        cap.paragraph_format.keep_with_next = True
        tbl = doc.add_table(rows=1, cols=len(headers))
        tbl.autofit = False
        for i, text in enumerate(headers):
            tbl.rows[0].cells[i].text = text
        for row in rows:
            cells = tbl.add_row().cells
            for i, text in enumerate(row):
                cells[i].text = str(text)
        pr = tbl._tbl.tblPr
        borders = OxmlElement('w:tblBorders')
        for edge in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement('w:' + edge)
            for key, val in [('val', 'single'), ('sz', '4'), ('color', '000000')]:
                border.set(qn('w:' + key), val)
            borders.append(border)
        pr.append(borders)
        repeat = OxmlElement('w:tblHeader')
        tbl.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in tbl.rows:
            row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
            for i, cell in enumerate(row.cells):
                if widths:
                    cell.width = Cm(widths[i])
                for para in cell.paragraphs:
                    para.style = doc.styles['Report Table']
                    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    para.paragraph_format.first_line_indent = Cm(0)
                    for run in para.runs:
                        run.font.name = 'Times New Roman'
                        run.font.size = Pt(12)
        p('')

    # Formatting-only template lets the report be rebuilt from the project archive.
    doc.save(ROOT / 'docs/report_template.docx')
    # Title follows Shapes4CW, typography and margins follow the supplied Word coursework.
    center('Министерство науки и высшего образования Российской Федерации')
    center('Федеральное государственное бюджетное образовательное учреждение высшего образования')
    center('«Волгоградский государственный технический университет»', after=16)
    center('Факультет электроники и вычислительной техники')
    center('Кафедра «ЭВМ и системы»', after=25)
    center('КОНТРОЛЬНАЯ РАБОТА', after=12)
    center('по дисциплине:')
    center(DISCIPLINE, after=15)
    center('на тему:')
    center(TITLE, after=25)
    para = p('Выполнил: студент группы САПР-2.1\nМаттиев Рустам Алимжонович', WD_ALIGN_PARAGRAPH.RIGHT)
    para.paragraph_format.first_line_indent = Cm(0)
    para.paragraph_format.space_after = Pt(18)
    para = p('Проверил:\nАндреев А. Е.', WD_ALIGN_PARAGRAPH.RIGHT)
    para.paragraph_format.first_line_indent = Cm(0)
    para.paragraph_format.space_after = Pt(18)
    center('Результат проверки: __________________________', after=25)
    center('Волгоград, 2026 г.')
    doc.add_page_break()
    center('Содержание')
    toc = p('', WD_ALIGN_PARAGRAPH.LEFT)
    toc.paragraph_format.first_line_indent = Cm(0)
    begin, instruction, separate, end = [OxmlElement(t) for t in ['w:fldChar', 'w:instrText', 'w:fldChar', 'w:fldChar']]
    begin.set(qn('w:fldCharType'), 'begin')
    instruction.set(qn('xml:space'), 'preserve')
    instruction.text = ' TOC \\o "1-2" \\h \\z \\u '
    separate.set(qn('w:fldCharType'), 'separate')
    end.set(qn('w:fldCharType'), 'end')
    for element in [begin, instruction, separate, end]:
        run = OxmlElement('w:r')
        run.append(element)
        toc._p.append(run)
    doc.add_page_break()

    h('Введение')
    p('В работе рассматривается развитие клиент-серверного приложения интернет-магазина товаров вселенной Warhammer. Исходной основой является курсовая работа первого года обучения, реализованная на Python и Django. Сохранены предметная область, каталог фракций и товаров, корзина и система скидок. Основное развитие связано с выделением облачного сервиса интеллектуального подбора и подключением двух самостоятельных клиентов к общему REST API.')
    p('Цель работы — разработать распределённое приложение, в котором пользователь может просматривать каталог, формировать заказ и получать рекомендации по пожеланиям и бюджету. Сервер магазина отвечает за достоверные цены, остатки и сохранение заказов; облачная функция использует внешнюю языковую модель для выбора товаров и объяснения результата. Решение проверяется через веб-интерфейс и отдельное настольное приложение.')
    p('Использованы Python 3.11, Django 5.2, Django REST Framework, SQLite, HTML, CSS, JavaScript и Tkinter. Облачная часть размещена в Cloudflare Workers, модель вызывается через Workers AI. В отличие от указанной в исходном задании платформы Yandex Cloud, в данной реализации по выбору автора используется Cloudflare с бесплатным суточным лимитом. Остальные архитектурные требования сохранены: два REST-сервиса, два клиента, внешний ИИ, документация API и UML.')

    h('1 Постановка задачи и анализ исходного приложения')
    h('1.1 Требования к разрабатываемой системе', 2)
    p('Необходимо доработать интернет-магазин так, чтобы клиенты взаимодействовали с его функциями через документированный HTTP-интерфейс. ИИ-подбор должен быть доступен из обоих клиентов, учитывать доступный каталог и общий бюджет, а также не изменять цены и наличие товаров по усмотрению модели.')
    table('Соответствие реализации требованиям контрольной работы', ['Требование', 'Реализация'], [
        ('Не менее двух REST-сервисов', 'Сервис магазина Django и отдельный сервис рекомендаций Cloudflare Worker.'),
        ('Сервис, связанный с ИИ', 'Workers AI: Llama 3.3 70B выбирает товары по текстовым пожеланиям.'),
        ('Облачная веб-функция', 'Опубликованный Worker с обработчиком fetch и маршрутами /health, /recommendations.'),
        ('Два клиента', 'Веб-клиент HTML/CSS/JavaScript и самостоятельный GUI-клиент Python/Tkinter.'),
        ('Документация REST API', 'Описание методов, полей, авторизации и ошибок; две спецификации OpenAPI.'),
        ('UML-диаграммы', 'Варианты использования, компоненты, классы, последовательность и развёртывание.')], [5, 12])
    h('1.2 Варианты использования', 2)
    p('Покупатель просматривает каталог без авторизации. Для персональной корзины, оформления заказа и ИИ-подбора он входит в систему. Администратор управляет каталогом и остатками. Внешним участником интеллектуального сценария является Workers AI, который получает только данные кандидатов и пожелания, необходимые для подбора. Варианты использования показаны на рисунке 1.')
    fig('docs/uml/use_cases.png', 'Диаграмма вариантов использования')
    h('1.3 Состояние исходной курсовой и внесённые исправления', 2)
    p('Исходная работа TPLab2-3 уже содержала сервер Django, веб-страницы и REST API. Однако страницы использовали обычные серверные представления, а наличие API не сопровождалось отдельным GUI-клиентом и облачным сервисом. В новой версии основные действия веб-клиента выполняются JavaScript-запросами к тому же API, который использует Tkinter.')
    table('Исправления исходной реализации', ['Проблема', 'Решение'], [
        ('Сериализатор корзины не соответствовал обратной связи моделей', 'Связь CartItem.cart имеет related_name="items"; API возвращает позиции и итоговые суммы.'),
        ('Заказ ссылался на удаляемые позиции корзины', 'Создана модель OrderItem с копией названия и цены покупки. Очистка корзины не удаляет историю.'),
        ('Дублировался маршрут списка товаров', 'Оставлен единый ProductViewSet с поиском, фильтрами и сортировкой.'),
        ('Изменение каталога было доступно обычным авторизованным пользователям', 'Для записи требуется роль администратора; публичное чтение сохранено.'),
        ('Недостаточная проверка количества и наличия', 'Валидация на уровне API, ограничения БД и условное уменьшение остатка в транзакции.')], [6, 11])

    h('2 Архитектура и серверная часть')
    h('2.1 Разделение системы на компоненты', 2)
    p('Сервис магазина является владельцем бизнес-данных: пользователей, каталога, корзин и заказов. Клиенты передают HTTP-запросы и показывают результаты, не открывая базу напрямую. Сервис рекомендаций развёртывается независимо, принимает список кандидатов и возвращает их идентификаторы с объяснениями. Workers AI выступает внешней платформенной функцией, используемой этим сервисом.')
    fig('docs/uml/components.png', 'Диаграмма компонентов системы')
    p('Код магазина разделён на модели, сериализаторы, API-обработчики и модуль services.py. Оформление заказа и проверка результатов подбора сосредоточены в сервисном модуле. Это обеспечивает одинаковое поведение веб-клиента и GUI. Облачный Worker не импортирует Django и не содержит SQLite-базу.')
    h('2.2 Модель данных', 2)
    p('Каталог описывается моделями Faction и Product. Товар содержит цену, остаток, категорию, фракцию, изображение, ключевые слова и признак пригодности для новичка. Cart принадлежит одному пользователю, а CartItem связывает корзину с товаром и количеством. В пределах корзины пара «корзина — товар» уникальна.')
    fig('docs/uml/classes.png', 'Диаграмма классов предметной области')
    p('Order содержит итоговую сумму, дату, статус и владельца. OrderItem хранит собственные product_name и unit_price. Ссылка на Product может стать null после удаления товара, но название, цена и количество в заказе сохраняются. Денежные значения представлены Decimal с двумя знаками после точки.')
    h('2.3 Корзина, скидки и оформление заказа', 2)
    p('Для категории STARTER_SET применяется скидка 10%. Эффективная цена вычисляется методом get_discounted_price() и используется при показе карточек, расчёте корзины, отборе кандидатов и создании заказа. Сервер не принимает итоговую сумму от клиента как достоверное значение.')
    p('При оформлении заказа сервер загружает позиции своей корзины, проверяет наличие каждого товара и условно уменьшает остаток запросом с условием stock >= quantity. Все изменения выполняются в одной транзакции. Если хотя бы один товар недоступен, уменьшение остальных остатков, создание заказа и очистка корзины отменяются. Повторное оформление уже очищенной корзины возвращает ошибку 400.')
    h('2.4 Наполнение каталога', 2)
    p('Каталог содержит 15 товаров: три позиции исходной курсовой и двенадцать добавленных. Для новых позиций загружены фотографии, сохранённые локально в media/products. Страницы-источники перечислены в image_sources.json. Описания, цены и остатки являются учебными данными. Исходные позиции не удалены; отсутствие Гвардии Смерти на складе используется для проверки исключения недоступных товаров.')
    import sys
    sys.path.insert(0, str(ROOT))
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'warhammer_project.settings')
    import django
    django.setup()
    from store.management.commands.seed_demo import CATALOG
    from decimal import Decimal
    catalog_rows = []
    for row in CATALOG:
        name, _, kind, price, _, _, _, _, _ = row
        effective = Decimal(price) * (Decimal('0.9') if kind == 'STARTER_SET' else Decimal('1'))
        category = dict(__import__('store.models', fromlist=['Product']).Product.PRODUCT_TYPES)[kind]
        catalog_rows.append((name, category, f'{effective:.2f}'))
    table('Учебный каталог и цены с учётом скидки', ['Товар', 'Категория', 'Цена, руб.'], catalog_rows, [9, 5, 3])
    p('Команда seed_demo создаёт отсутствующие позиции и демонстрационных пользователей. Повторный запуск не дублирует записи, не меняет существующие пароли и не восстанавливает купленные остатки. Для явного восстановления учебных остатков предусмотрен параметр --reset-stock.')

    h('3 Проектирование REST API')
    h('3.1 Общие соглашения и авторизация', 2)
    p('Базовый адрес API магазина: http://127.0.0.1:8000/api/v1/. Запросы и ответы используют UTF-8 JSON. Списки представлены массивами без пагинации в учебной версии. Токен выдаётся методом auth/login/ и передаётся в заголовке Authorization: Token <token>. При выходе токен отзывается, поэтому его использование из другого клиента также прекращает работать.')
    p('Просмотр каталога и фракций публичен. Корзина, заказы и рекомендации требуют действующего токена. Создание, изменение и удаление товаров и фракций разрешены только администраторам. Для обращения к чужой позиции корзины или чужому заказу API возвращает 404. Документация OpenAPI доступна по /api/schema/, интерактивное представление — по /api/docs/.')
    h('3.2 Методы сервиса магазина', 2)
    table('Основные методы REST API магазина', ['Метод и путь', 'Назначение', 'Успех'], [
        ('POST auth/login/', 'Вход: username, password', '200'), ('POST auth/logout/', 'Отзыв токена', '204'),
        ('GET auth/me/', 'Текущий пользователь', '200'), ('GET factions/', 'Список фракций', '200'),
        ('GET factions/{id}/', 'Фракция по ID', '200'), ('GET products/', 'Каталог с фильтрами', '200'),
        ('GET products/{id}/', 'Карточка товара', '200'), ('POST products/, factions/', 'Создание записи администратором', '201'),
        ('PUT/PATCH products/{id}/, factions/{id}/', 'Полное/частичное изменение администратором', '200'),
        ('DELETE products/{id}/, factions/{id}/', 'Удаление администратором', '204'),
        ('GET cart/', 'Состав и сумма своей корзины', '200'), ('POST cart/', 'Добавление product_id и quantity', '201'),
        ('PATCH cart/items/{id}/', 'Изменение quantity своей позиции', '200'), ('DELETE cart/items/{id}/', 'Удаление своей позиции', '204'),
        ('GET orders/', 'История собственных заказов', '200'), ('POST orders/', 'Заказ из текущей корзины', '201'),
        ('GET orders/{id}/', 'Состав собственного заказа', '200'), ('POST recommendations/', 'Интеллектуальный подбор', '200')], [7, 8.5, 1.5])
    p('Каталог поддерживает параметры search, faction, type, min_price, max_price, in_stock и ordering. Границы цены относятся к стоимости после скидки. Допустимые сортировки: id, price, -price, name. Некорректный идентификатор, неизвестная категория, отрицательная цена и минимальная цена выше максимальной приводят к ошибке 400.')
    h('3.3 Данные запроса интеллектуального подбора', 2)
    table('Поля RecommendationRequest', ['Поле', 'Тип', 'Ограничение'], [
        ('preferences', 'string', 'Обязательно; 5–1200 символов'), ('budget', 'decimal string', 'Обязательно; 1–1 000 000 руб., до двух дробных знаков'),
        ('max_items', 'integer', '1–5 разных товаров; по умолчанию 3'), ('faction', 'integer/null', 'Необязательный положительный ID фракции'),
        ('product_type', 'enum', 'Необязательный код категории')], [4.5, 4, 8.5])
    code('''POST /api/v1/recommendations/
Authorization: Token <токен пользователя>
Content-Type: application/json

{
  "preferences": "Я новичок. Хочу начать собирать космодесант.",
  "budget": "6000.00",
  "max_items": 3
}''')
    p('Ответ содержит массив items с полной карточкой товара, количеством, объяснением reason и стоимостью позиции. Дополнительно возвращаются total_price, budget, explanation, model и cached. Отсутствие подходящих кандидатов является корректным пустым результатом, а не сетевой ошибкой. В таком случае обращение к модели не выполняется.')
    h('3.4 Контракт облачного сервиса и ошибки', 2)
    p('Worker предоставляет публичный GET /health и защищённый POST /recommendations. Django передаёт пожелания, бюджет, max_items и массив products, содержащий не более 50 кандидатов. Для товара обязательны id, name, price и stock; дополнительные поля дают модели контекст фракции, категории и пригодности для новичка. Размер HTTP-тела ограничен 160 000 байт.')
    p('Авторизация между Django и Worker использует отдельный случайный ключ: Authorization: Bearer <service_key>. Он не совпадает с пользовательским токеном и Cloudflare API Token. Ответ Worker содержит только проверенные product_id, quantity, reason и идентификатор модели. Полная спецификация независимого сервиса сохранена в cloud_openapi.yaml.')
    table('Основные коды ошибок', ['HTTP', 'Причина', 'Поведение клиента'], [
        ('400', 'Некорректные поля, превышение остатка, пустая корзина', 'Показать сообщение, дать исправить данные'),
        ('401', 'Нет действующего токена или неверный ключ', 'Предложить вход; служебную ошибку скрыть за 503'),
        ('403', 'Недостаточно прав администратора', 'Показать отказ в операции'),
        ('404', 'Нет объекта или он принадлежит другому пользователю', 'Не показывать чужие данные'),
        ('429', 'Превышение частоты запросов', 'Предложить повторить позже'),
        ('502', 'Worker не получил корректный ответ модели', 'Django преобразует в 503 для клиента'),
        ('503', 'Облако недоступно, не настроено или ответ некорректен', 'Показать понятное сообщение без фиктивных рекомендаций')], [1.5, 8, 7.5])
    p('Полная документация API.md дополнительно описывает форматы Product, Cart, Order, ограничения количества, административный CRUD и служебные ошибки 405, 413 и 415. Облачные ключи и исходные диагностические ответы провайдера не передаются конечным клиентам.')

    h('4 Облачный сервис интеллектуального подбора')
    h('4.1 Выбор платформы и модели', 2)
    p('Cloudflare Worker реализует небольшую сетевую функцию, вызываемую по HTTPS. Для генерации используется модель @cf/meta/llama-3.3-70b-instruct-fp8-fast, доступная через Workers AI. Подключение к модели задаётся binding с именем AI; обработчик обращается к нему как env.AI.run(). Самостоятельное размещение модели и локальная видеокарта не требуются [4–6].')
    h('4.2 Алгоритм формирования рекомендаций', 2)
    p('Сначала Django проверяет авторизацию и поля запроса, затем отбирает товары с положительным остатком, применяет ограничения категории и фракции и исключает товары, которые по отдельности дороже бюджета. В модель передаются действительные цены после скидки, описания и теги. Общая фракция не включается при заданном строгом фильтре faction.')
    p('Worker проверяет служебный ключ, структуру и размер тела. Системный промпт требует выбирать только переданные товары, учитывать пожелания и стоимость всего набора, давать короткие объяснения по-русски и возвращать JSON. Пожелания и описания явно представлены как данные, а не инструкции. Формат ответа ограничивается JSON Schema, однако на корректность схемы как единственный контроль система не полагается.')
    p('После вызова модели Worker удаляет неизвестные и повторяющиеся идентификаторы, некорректные количества и позиции, превышающие бюджет. Django повторно читает актуальные цены и остатки и пересчитывает сумму через Decimal. Результат кешируется на пять минут; ключ включает запрос и характеристики кандидатов. Даже кешированный ответ проверяется перед выдачей пользователю.')
    h('4.3 Последовательность взаимодействия компонентов', 2)
    p('На рисунке показан основной сценарий при отсутствии готового результата в кеше. При повторном запросе с неизменными кандидатами обращение к облаку пропускается. При отсутствии кандидатов сервер сразу возвращает пустой массив. При сетевой ошибке или некорректном JSON пользователю возвращается ошибка доступности сервиса.')
    fig('docs/uml/sequence.png', 'Диаграмма последовательности ИИ-подбора')
    h('4.4 Создание и размещение веб-функции', 2)
    p('Развёртывание выполнено через официальный REST API Cloudflare без Wrangler. В аккаунте создан токен с правами Workers AI Read/Edit и Workers Scripts Edit в пределах выбранного аккаунта. Идентификатор аккаунта и токен хранятся только в локальном .env. В архив и отчёт они не включаются.')
    p('Скрипт deploy_cloudflare.py считывает worker.mjs, формирует multipart/form-data с метаданными ES-модуля и загружает его методом PUT /accounts/{account_id}/workers/scripts/{script_name}. Метаданные задают main_module, compatibility_date, AI binding, идентификатор модели и секрет SERVICE_API_KEY. Далее включается адрес workers.dev, а URL и отдельный служебный ключ записываются в .env [7].')
    code('''python scripts/check_cloudflare.py
python scripts/deploy_cloudflare.py''')
    deployment = json.loads((ROOT/'docs/deployment.json').read_text(encoding='utf-8'))
    p('Фактически опубликованный сервис: ' + deployment['url'] + '. Проверочный адрес: ' + deployment['url'] + '/health. Наличие веб-функции подтверждено ответом опубликованного Worker, а работа модели — отдельным реальным интеграционным запросом.')
    live = json.loads((ROOT/'docs/live_validation.json').read_text(encoding='utf-8'))
    table('Результат реального обращения Django → Worker → Workers AI', ['Параметр', 'Значение'], [
        ('HTTP-статус', str(live['http_status'])), ('Модель', live['response']['model']),
        ('Бюджет', live['response']['budget'] + ' руб.'), ('Количество разных товаров', len(live['response']['items'])),
        ('Сумма набора', live['response']['total_price'] + ' руб.'),
        ('Проверки', 'Доступность Worker, реальный ответ модели, наличие товаров, корректный пересчёт и соблюдение бюджета.')], [5, 12])
    p('Результат этого обращения сохранён без токенов в docs/live_validation.json. Тексты и состав рекомендаций могут отличаться между обращениями к генеративной модели; скриншоты клиентов показывают фактические результаты соответствующих проверочных запусков.')
    h('4.5 Ограничения бесплатного режима', 2)
    p('По документации Cloudflare на дату выполнения работы Workers Free предоставляет 10 000 Neurons в сутки. Это вычислительные единицы, поэтому число запросов зависит от длины контекста и ответа. При исчерпании бесплатного лимита запросы завершаются ошибкой до обновления лимита; платный тариф в рамках работы не подключался. Отдельные модели требуют оплаты, выбранная модель проверена в используемом аккаунте [8].')
    p('Для экономии запросов введены кеширование и ограничение ИИ-подбора до 10 обращений в минуту на пользователя. В модели передаются только краткие характеристики не более 50 товаров, число рекомендуемых позиций ограничено пятью. Эти меры подходят учебному каталогу, но не заменяют общую систему квот для многопроцессного публичного сервиса.')

    h('5 Реализация клиентских приложений')
    h('5.1 Веб-клиент: каталог и фильтры', 2)
    p('Веб-клиент реализован без отдельного фреймворка: сервер отдаёт HTML-оболочку, CSS и JavaScript, а каталог и пользовательские действия выполняются через fetch к REST API. Данные модели экранируются перед включением в HTML. Карточки содержат фотографию, фракцию, категорию, описание, цену со скидкой и доступность.')
    fig('docs/screenshots/web_catalog.png', 'Веб-клиент: каталог товаров', maxheight=17)
    p('Фильтры позволяют искать товар, выбирать фракцию и категорию, ограничивать диапазон цены и наличие. Сортировка выполняется сервером. Вёрстка адаптируется к узкому экрану; в браузерной проверке ширина 390 пикселей не вызвала горизонтального переполнения.')
    h('5.2 Веб-клиент: ИИ-подбор, корзина и заказы', 2)
    p('Форма подбора принимает свободный текст, общий бюджет, необязательные фильтры и ограничение числа товаров. Во время обращения кнопка показывает ожидание. В результате отображаются товарные карточки с объяснениями и общей проверенной стоимостью. Каждую рекомендацию можно добавить в корзину с предложенным количеством.')
    fig('docs/screenshots/web_recommendations.png', 'Веб-клиент: реальный результат ИИ-подбора', maxheight=18)
    p('Корзина позволяет менять количество и удалять позиции. Оформление вызывает POST orders/; сервер возвращает сохранённый заказ, а клиент открывает историю. Интерфейс отдельно обрабатывает отсутствие товаров, пустую корзину, необходимость входа и недоступность сервиса.')
    fig('docs/screenshots/web_cart.png', 'Веб-клиент: корзина перед оформлением', maxheight=15)
    fig('docs/screenshots/web_orders.png', 'Веб-клиент: сохранённые заказы', maxheight=15)
    h('5.3 Самостоятельный настольный клиент', 2)
    p('Второй клиент реализован на Python/Tkinter. Он не импортирует Django и не открывает SQLite. Модуль desktop/client.py выполняет HTTP-запросы и хранит токен только в памяти. В интерфейсе задаётся адрес сервера, доступны вход, каталог с фильтрами, просмотр изображения и описания, ИИ-подбор, корзина и история заказов.')
    fig('docs/screenshots/desktop_catalog.png', 'Настольный клиент: каталог и карточка товара', maxheight=15)
    p('Сетевые операции выполняются в пуле потоков. Результаты передаются в главный поток через очередь, поэтому интерфейс продолжает отвечать во время ожидания модели. Текстовые объяснения доступны в таблице и в области выбранной рекомендации. Предусмотрены таймаут и сообщения об ошибках.')
    fig('docs/screenshots/desktop_recommendations.png', 'Настольный клиент: ответ настоящей модели', maxheight=15)
    p('Работа GUI проверена через реальный сервер: выполнены вход, запрос рекомендаций, добавление позиции, оформление заказа и загрузка истории. Учётные записи и корзина общие для клиентов. Выход отзывает единый пользовательский токен, поэтому другой клиент с прежним токеном должен войти повторно.')

    h('6 Тестирование и запуск системы')
    h('6.1 Автоматизированные проверки', 2)
    p('Для сервиса магазина выполнено 25 тестов Django REST Framework. Проверяются публичный каталог, скидка, фильтрация по эффективной цене, некорректные параметры, права администратора, вход и отзыв токена, корзина, наличие, приватность заказов и снимки цены. Отдельные проверки подтверждают откат транзакции при недостатке товара, невозможность повторного заказа из пустой корзины и идемпотентность наполнения каталога.')
    p('Проверки ИИ-интеграции с подменой только сетевого вызова охватывают неизвестные идентификаторы, дубликаты, превышение остатков и общего бюджета, кеширование, недоступность облака, некорректный JSON и ограничение частоты. Эти тесты не расходуют лимит модели. Семь независимых тестов Worker проверяют health, авторизацию, валидацию, фильтрацию результата, пустой каталог, ошибку модели и размер тела.')
    table('Результаты проверки системы', ['Уровень', 'Результат'], [
        ('Django / REST API', '25 тестов выполнены успешно.'), ('Cloudflare Worker, локальный обработчик', '7 тестов выполнены успешно.'),
        ('OpenAPI магазина', 'Схема сгенерирована и проверена командой spectacular --validate.'),
        ('Реальная облачная интеграция', 'HTTP 200, непустой результат модели, сумма не выше бюджета.'),
        ('Веб-клиент в Chrome', '7 проверок; нет JavaScript-ошибок; работают фильтр, вход, ИИ, корзина, заказ и адаптивная вёрстка.'),
        ('GUI в интерактивной Windows-сессии', '6 проверок; каталог, авторизация, реальный ИИ, корзина, оформление и история.'),
        ('Переносимость', 'В чистой копии с шаблоном .env созданы БД и 15 товаров; проверены повторное наполнение, изображения, вход, корзина, заказ и OpenAPI.')], [6, 11])
    code('''python manage.py test store
node --test cloud_function/worker.test.mjs
python manage.py spectacular --file docs/openapi.yaml --validate''')
    h('6.2 Развёртывание и зависимости', 2)
    p('Основной сервер запускается локально или на компьютере в частной сети; отдельный сервис подбора уже размещён в облаке. Браузерный и настольный клиенты обращаются к серверу магазина. Изображения раздаются из локальной папки, а связь с облаком требуется только для новых ИИ-запросов.')
    fig('docs/uml/deployment.png', 'Диаграмма развёртывания')
    p('На другом компьютере для полного учебного запуска требуются Python 3.11 или новее с pip и Tcl/Tk, современный браузер и доступ в интернет для первоначальной установки зависимостей и ИИ-подбора. Зависимости магазина перечислены в requirements.txt. Node.js, npm, Wrangler, Docker, Word и отдельный сервер БД для эксплуатации приложения не нужны.')
    h('6.3 Порядок установки на другом устройстве', 2)
    p('Проект следует распаковать в папку с правом записи. В Windows команда setup.cmd создаёт виртуальное окружение, устанавливает пакеты, применяет миграции и выполняет seed_demo. Файл .env.example служит шаблоном; приватный .env в распространяемый архив не включён. Для использования уже размещённого сервиса достаточно перенести свой RECOMMENDATIONS_URL и RECOMMENDATIONS_API_KEY. Cloudflare API Token нужен только при размещении Worker в своём аккаунте.')
    code('''py -3 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe manage.py migrate
.\\.venv\\Scripts\\python.exe manage.py seed_demo
.\\.venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8000''')
    p('После запуска сервера веб-клиент открывается по адресу http://127.0.0.1:8000/. Во втором окне запускается настольный клиент. Для Windows подготовлены run_server.cmd и run_desktop.cmd; они рассчитаны на окружение, созданное setup.cmd. Активация виртуального окружения и изменение политики PowerShell не требуются.')
    code('''.\\.venv\\Scripts\\python.exe desktop\\app.py''')
    table('Демонстрационные учётные записи', ['Роль', 'Логин', 'Пароль'], [
        ('Покупатель', 'demo', 'WarhammerDemo2026!'), ('Администратор', 'admin', 'WarhammerAdmin2026!')], [5, 4, 8])
    p('Демонстрационные пароли относятся только к локальному учебному наполнению. Свой аккаунт администратора создаётся командой manage.py createsuperuser. Облачные ключи не передаются браузеру и GUI. На компьютере, используемом только для GUI, достаточно файлов desktop/, Python/Tkinter и Pillow; серверные зависимости и ключи ему не требуются.')
    h('6.4 Запуск клиентов по локальной сети и ограничения', 2)
    p('Для доступа со второго компьютера сервер запускается на 0.0.0.0:8000, а в DJANGO_ALLOWED_HOSTS добавляется его фактический LAN IP. В брандмауэре разрешаются входящие соединения к порту 8000 в частной сети. Браузер открывает http://<LAN-IP>:8000/, а в GUI тот же адрес задаётся в поле «Сервер» до входа.')
    p('Учебная конфигурация использует SQLite и встроенный сервер Django. Она не является публичной промышленной установкой: для такой эксплуатации потребуются HTTPS, WSGI-сервер, раздача статики, собственный SECRET_KEY и отдельное управление паролями. Кеш и счётчики частоты находятся в памяти процесса. Подбор ограничен небольшим каталогом, не обучает собственную модель, не гарантирует игровую совместимость армии и не резервирует товар.')

    h('Заключение')
    p('Разработана новая версия интернет-магазина Warhammer с общей серверной логикой и двумя клиентами. Исправлены выдача корзины, сохранение позиций заказа, проверка прав и маршрутизация каталога. Каталог расширен до 15 товаров и снабжён локальными изображениями. Веб-интерфейс и самостоятельный Tkinter-клиент выполняют пользовательские действия через документированный REST API.')
    p('В Cloudflare Workers размещён отдельный сервис рекомендаций, который вызывает настоящую модель Workers AI. Реализованы ограничение кандидатов, структурированный ответ, проверка наличия и бюджета, кеширование и обработка отказов. Работоспособность подтверждена автоматизированными тестами и реальными сценариями обоих клиентов. Подготовлены UML, OpenAPI, исходники, инструкции переноса и отчёт в редактируемом и PDF-форматах.')

    h('Список использованных источников')
    sources = [
        'Задание на контрольную работу по МиСА: Tasks_MiSA-23.docx. Учебные материалы преподавателя.',
        'Образец оформления контрольной работы: Shapes4CW.pdf. Учебные материалы преподавателя.',
        'Маттиев Р. А. Разработка клиент-серверного приложения: веб-приложение по продаже настольных игр. Курсовая работа. Волгоград, 2025. ПЗ_Маттиев_САПР-1.1.docx; исходный проект TPLab2-3.',
        'Cloudflare. Workers AI: Workers Bindings. URL: https://developers.cloudflare.com/workers-ai/get-started/workers-wrangler/ (дата обращения: 19.11.2026).',
        'Cloudflare. Llama 3.3 70B Instruct FP8 Fast. URL: https://developers.cloudflare.com/workers-ai/models/llama-3.3-70b-instruct-fp8-fast/ (дата обращения: 19.11.2026).',
        'Cloudflare. Workers AI: JSON Mode. URL: https://developers.cloudflare.com/workers-ai/features/json-mode/ (дата обращения: 19.11.2026).',
        'Cloudflare API. Upload Worker. URL: https://developers.cloudflare.com/api/resources/workers/subresources/scripts/methods/update/ (дата обращения: 19.11.2026).',
        'Cloudflare. Workers AI Pricing. URL: https://developers.cloudflare.com/workers-ai/platform/pricing/ (дата обращения: 19.11.2026).',
        'Django Software Foundation. Django 5.2 documentation. URL: https://docs.djangoproject.com/en/5.2/ (дата обращения: 19.11.2026).',
        'Django REST framework. Serializers. URL: https://www.django-rest-framework.org/api-guide/serializers/ (дата обращения: 19.11.2026).',
        'Wargames Emporium. Каталог товаров и фотографии. URL: https://www.wargamesemporium.co.uk/ (дата обращения: 19.11.2026). Точные страницы сохранены в docs/image_sources.json.'
    ]
    for index, text in enumerate(sources, 1):
        p(str(index) + '. ' + text)

    doc.add_page_break()
    h('Приложение А. Фрагмент реального ответа сервиса')
    p('Ниже приведён сокращённый ответ реальной проверки. Полные карточки и метаданные сохранены в docs/live_validation.json. Токены авторизации в результат не включены.')
    slim = {'items': [{'product_id': i['product']['id'], 'name': i['product']['name'], 'quantity': i['quantity'],
                       'reason': i['reason'], 'total_price': i['total_price']} for i in live['response']['items']],
            'total_price': live['response']['total_price'], 'budget': live['response']['budget'], 'model': live['response']['model']}
    # Wrap long natural-language strings for readable printed code.
    import textwrap
    raw = json.dumps(slim, ensure_ascii=False, indent=2)
    code('\n'.join('\n'.join(textwrap.wrap(line, 90, subsequent_indent='      ', break_long_words=False, break_on_hyphens=False)) if len(line)>90 else line for line in raw.splitlines()))
    # Word will update the TOC, page fields and pagination before PDF export.
    update = OxmlElement('w:updateFields')
    update.set(qn('w:val'), 'true')
    doc.settings.element.append(update)
    path = OUT / 'Контрольная_Маттиев_МиСАКСИИ.docx'
    doc.save(path)
    manifest = {'docx': path.name, 'font': 'Times New Roman', 'body_size_pt': 14, 'body_line_spacing': 1.5,
                'first_line_indent_cm': 1.25, 'page_mm': [210, 297],
                'margins_mm': {a: round(getattr(section, a).mm, 2) for a in ['top_margin', 'bottom_margin', 'left_margin', 'right_margin']},
                'figures': figures[0], 'tables': tables[0], 'group': 'САПР-2.1', 'discipline': DISCIPLINE}
    (ROOT/'docs/report_format.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Word report created. Figures:', figures[0], 'tables:', tables[0])


if __name__ == '__main__':
    main()
