"""Tkinter client; run: python desktop/app.py --server http://127.0.0.1:8000"""
import argparse
import ctypes
import io
import os
import queue
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import urlencode
from urllib.request import urlopen
from PIL import Image, ImageTk
from client import StoreClient

if os.name == 'nt':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass

CATEGORIES = {'Все категории': '', 'Миниатюры': 'MINIATURE', 'Стартовые наборы': 'STARTER_SET',
              'Краски': 'PAINT', 'Аксессуары': 'ACCESSORY', 'Книги правил': 'BOOK'}


def money(value):
    return f'{float(value):,.2f} ₽'.replace(',', ' ')


class StoreApp(tk.Tk):
    def __init__(self, server):
        super().__init__()
        self.title('Warhammer AI Store — настольный клиент')
        self.geometry('1200x820')
        self.minsize(980, 690)
        self.configure(bg='#f4f5f7')
        self.client = StoreClient(server)
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.messages = queue.Queue()
        self.pending = 0
        self.products, self.factions, self.recommendations, self.cart_items = {}, {}, {}, {}
        self.preview_image = None
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TFrame', background='#f4f5f7')
        style.configure('TLabel', background='#f4f5f7', foreground='#202d3d')
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        style.configure('TButton', padding=(13, 8))
        style.configure('Accent.TButton', foreground='white', background='#dc6b36')
        style.configure('Treeview', rowheight=32, font=('Segoe UI', 10))
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=8)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.build()
        self.after(70, self.poll)
        self.load_catalog()

    def task(self, work, done):
        self.pending += 1
        self.status.set('Выполняется запрос…')
        def run():
            try:
                result, error = work(), None
            except Exception as exc:
                result, error = None, str(exc)
            self.messages.put((done, result, error))
        self.pool.submit(run)

    def poll(self):
        while True:
            try:
                done, result, error = self.messages.get_nowait()
            except queue.Empty:
                break
            self.pending -= 1
            if error:
                self.status.set(error)
                messagebox.showerror('Не удалось выполнить запрос', error, parent=self)
            else:
                done(result)
                if not self.pending:
                    self.status.set('Готово')
        self.after(70, self.poll)

    def build(self):
        header = tk.Frame(self, bg='#111923', padx=22, pady=15)
        header.pack(fill='x')
        tk.Label(header, text='W  /  WARHAMMER AI STORE', fg='#f28b58', bg='#111923', font=('Segoe UI', 19, 'bold')).pack(side='left')
        tk.Label(header, text='Настольный клиент', fg='#acb9cc', bg='#111923', font=('Segoe UI', 10)).pack(side='right')
        auth = ttk.Frame(self, padding=(20, 14))
        auth.pack(fill='x')
        self.server = tk.StringVar(value=self.client.base_url)
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        ttk.Label(auth, text='Сервер').grid(row=0, column=0, sticky='w', padx=(0, 8))
        ttk.Entry(auth, textvariable=self.server, width=27).grid(row=0, column=1, padx=(0, 14))
        ttk.Label(auth, text='Логин').grid(row=0, column=2)
        ttk.Entry(auth, textvariable=self.username, width=15).grid(row=0, column=3, padx=8)
        ttk.Label(auth, text='Пароль').grid(row=0, column=4)
        ttk.Entry(auth, textvariable=self.password, show='•', width=17).grid(row=0, column=5, padx=8)
        self.login_button = ttk.Button(auth, text='Войти', command=self.login)
        self.login_button.grid(row=0, column=6, padx=5)
        self.identity = tk.StringVar(value='Гость')
        ttk.Label(auth, textvariable=self.identity).grid(row=0, column=7, padx=12)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True, padx=20, pady=(0, 12))
        self.catalog_tab, self.ai_tab, self.cart_tab, self.orders_tab = [ttk.Frame(self.tabs, padding=18) for _ in range(4)]
        for frame, title in [(self.catalog_tab, 'Каталог'), (self.ai_tab, 'Подбор с ИИ'), (self.cart_tab, 'Корзина'), (self.orders_tab, 'Мои заказы')]:
            self.tabs.add(frame, text=title)
        self.build_catalog()
        self.build_advisor()
        self.build_cart()
        self.build_orders()
        self.tabs.bind('<<NotebookTabChanged>>', self.tab_changed)
        self.status = tk.StringVar(value='Подключаемся к серверу…')
        ttk.Label(self, textvariable=self.status, padding=(22, 8)).pack(fill='x')

    def tree(self, parent, columns, widths):
        holder = ttk.Frame(parent)
        holder.pack(fill='both', expand=True)
        tree = ttk.Treeview(holder, columns=list(columns), show='headings', selectmode='browse', height=4)
        for name, label in columns.items():
            tree.heading(name, text=label)
            tree.column(name, width=widths.get(name, 100), minwidth=60)
        scroll = ttk.Scrollbar(holder, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        return tree

    def build_catalog(self):
        bar = ttk.Frame(self.catalog_tab)
        bar.pack(fill='x', pady=(0, 16))
        self.search, self.category, self.faction = tk.StringVar(), tk.StringVar(value='Все категории'), tk.StringVar(value='Все фракции')
        self.max_price = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search, width=20).pack(side='left', padx=(0, 8))
        ttk.Combobox(bar, textvariable=self.category, values=list(CATEGORIES), state='readonly', width=19).pack(side='left', padx=5)
        self.faction_combo = ttk.Combobox(bar, textvariable=self.faction, values=['Все фракции'], state='readonly', width=16)
        self.faction_combo.pack(side='left', padx=5)
        ttk.Label(bar, text='До, ₽').pack(side='left', padx=(8, 3))
        ttk.Entry(bar, textvariable=self.max_price, width=10).pack(side='left')
        ttk.Button(bar, text='Найти', command=self.load_catalog).pack(side='left', padx=10)
        self.product_tree = self.tree(self.catalog_tab, {'name': 'Товар', 'category': 'Категория', 'faction': 'Фракция', 'price': 'Цена', 'stock': 'Остаток'},
                                      {'name': 350, 'category': 160, 'faction': 120, 'price': 120, 'stock': 75})
        self.product_tree.bind('<<TreeviewSelect>>', self.product_selected)
        detail = ttk.Frame(self.catalog_tab, padding=(0, 18, 0, 0))
        detail.pack(fill='x')
        self.image_label = ttk.Label(detail)
        self.image_label.pack(side='left', padx=(0, 20))
        self.product_description = tk.StringVar(value='Выберите товар, чтобы посмотреть описание.')
        ttk.Label(detail, textvariable=self.product_description, wraplength=700, justify='left').pack(side='left', fill='x', expand=True)
        ttk.Button(detail, text='В корзину', style='Accent.TButton', command=self.add_catalog).pack(side='right')

    def build_advisor(self):
        ttk.Label(self.ai_tab, text='Найдём то, что подходит вам', style='Title.TLabel').pack(anchor='w', pady=(0, 12))
        ttk.Label(self.ai_tab, text='Опишите интересы, опыт и предпочтения. Все товары вместе будут в пределах бюджета.').pack(anchor='w')
        self.preferences = tk.Text(self.ai_tab, height=4, wrap='word', font=('Segoe UI', 11), relief='solid', bd=1)
        self.preferences.pack(fill='x', pady=12)
        self.preferences.insert('1.0', 'Я новичок. Хочу начать собирать космодесант и попробовать покраску.')
        row = ttk.Frame(self.ai_tab)
        row.pack(fill='x', pady=(0, 15))
        self.budget = tk.StringVar(value='6000')
        self.ai_category = tk.StringVar(value='Все категории')
        self.ai_faction = tk.StringVar(value='Все фракции')
        ttk.Label(row, text='Бюджет, ₽').pack(side='left')
        ttk.Entry(row, textvariable=self.budget, width=12).pack(side='left', padx=8)
        ttk.Combobox(row, textvariable=self.ai_category, values=list(CATEGORIES), width=19, state='readonly').pack(side='left', padx=8)
        self.ai_faction_combo = ttk.Combobox(row, textvariable=self.ai_faction, values=['Все фракции'], width=16, state='readonly')
        self.ai_faction_combo.pack(side='left', padx=8)
        self.ai_button = ttk.Button(row, text='Подобрать товары', style='Accent.TButton', command=self.ask_ai)
        self.ai_button.pack(side='left', padx=8)
        self.recommend_tree = self.tree(self.ai_tab, {'name': 'Товар', 'quantity': 'Количество', 'price': 'Стоимость', 'reason': 'Почему подходит'},
                                        {'name': 300, 'quantity': 90, 'price': 115, 'reason': 460})
        self.recommend_tree.bind('<<TreeviewSelect>>', self.recommend_selected)
        self.ai_explanation = tk.StringVar(value='Рекомендации появятся здесь после запроса.')
        ttk.Label(self.ai_tab, textvariable=self.ai_explanation, wraplength=1050).pack(anchor='w', pady=12)
        ttk.Button(self.ai_tab, text='Добавить выбранный товар в корзину', command=self.add_recommendation).pack(anchor='e')

    def build_cart(self):
        ttk.Label(self.cart_tab, text='Ваша корзина', style='Title.TLabel').pack(anchor='w', pady=(0, 15))
        self.cart_tree = self.tree(self.cart_tab, {'name': 'Товар', 'quantity': 'Количество', 'unit': 'Цена за шт.', 'total': 'Стоимость'},
                                   {'name': 520, 'quantity': 120, 'unit': 150, 'total': 160})
        row = ttk.Frame(self.cart_tab, padding=(0, 16))
        row.pack(fill='x')
        self.quantity = tk.StringVar(value='1')
        ttk.Spinbox(row, from_=1, to=999, textvariable=self.quantity, width=6).pack(side='left')
        ttk.Button(row, text='Изменить количество', command=self.update_quantity).pack(side='left', padx=8)
        ttk.Button(row, text='Удалить', command=self.remove_item).pack(side='left', padx=8)
        ttk.Button(row, text='Обновить', command=self.load_cart).pack(side='left', padx=8)
        self.cart_total = tk.StringVar(value='Итого: 0 ₽')
        ttk.Label(row, textvariable=self.cart_total, font=('Segoe UI', 13, 'bold')).pack(side='right')
        self.checkout_button = ttk.Button(self.cart_tab, text='Оформить заказ', style='Accent.TButton', command=self.checkout)
        self.checkout_button.pack(anchor='e')
        ttk.Label(self.cart_tab, text='Учебный магазин: оформление заказа не выполняет списание денег.').pack(anchor='w', pady=12)

    def build_orders(self):
        ttk.Label(self.orders_tab, text='Мои заказы', style='Title.TLabel').pack(anchor='w', pady=(0, 15))
        self.orders_tree = self.tree(self.orders_tab, {'id': 'Заказ', 'date': 'Дата', 'total': 'Итого', 'status': 'Статус', 'items': 'Состав заказа'},
                                     {'id': 70, 'date': 165, 'total': 120, 'status': 120, 'items': 550})
        ttk.Button(self.orders_tab, text='Обновить заказы', command=self.load_orders).pack(anchor='e', pady=14)

    def need_login(self):
        if self.client.token:
            return True
        messagebox.showinfo('Вход', 'Сначала введите логин и пароль и нажмите «Войти».', parent=self)
        return False

    def login(self):
        if self.client.token:
            self.task(self.client.logout, lambda _: self.logged_out())
            return
        self.client.base_url = self.server.get().strip().rstrip('/')
        username, password = self.username.get(), self.password.get()
        if not username or not password:
            messagebox.showinfo('Вход', 'Введите логин и пароль.', parent=self)
            return
        self.task(lambda: self.client.login(username, password), self.logged_in)

    def logged_in(self, user):
        self.identity.set(user['username'])
        self.password.set('')
        self.login_button.configure(text='Выйти')
        self.load_cart()

    def logged_out(self):
        self.identity.set('Гость')
        self.login_button.configure(text='Войти')
        self.cart_tree.delete(*self.cart_tree.get_children())
        self.orders_tree.delete(*self.orders_tree.get_children())
        self.recommend_tree.delete(*self.recommend_tree.get_children())
        self.cart_total.set('Итого: 0 ₽')

    def load_catalog(self):
        self.client.base_url = self.server.get().strip().rstrip('/')
        params = {'search': self.search.get(), 'type': CATEGORIES[self.category.get()], 'max_price': self.max_price.get()}
        if self.faction.get() in self.factions:
            params['faction'] = self.factions[self.faction.get()]
        params = {k: v for k, v in params.items() if v}
        self.task(lambda: (self.client.request('products/?' + urlencode(params)), self.client.request('factions/')), self.catalog_loaded)

    def catalog_loaded(self, result):
        products, factions = result
        self.products = {p['id']: p for p in products}
        self.factions = {f['name']: f['id'] for f in factions}
        values = ['Все фракции'] + list(self.factions)
        self.faction_combo.configure(values=values)
        self.ai_faction_combo.configure(values=values)
        self.product_tree.delete(*self.product_tree.get_children())
        for p in products:
            self.product_tree.insert('', 'end', iid=str(p['id']), values=(p['name'], p['category_label'],
                p['faction']['name'] if p['faction'] else 'Общие товары', money(p['discounted_price']), p['stock']))
        if products:
            self.product_tree.selection_set(str(products[0]['id']))

    def product_selected(self, event=None):
        selected = self.product_tree.selection()
        if not selected:
            return
        p = self.products[int(selected[0])]
        self.product_description.set(p['name'] + '\n\n' + p['description'] + '\n\nЦена: ' + money(p['discounted_price']))
        if p.get('image'):
            pid, image_url = p['id'], p['image']
            def image_work():
                with urlopen(image_url, timeout=10) as response:
                    image = Image.open(io.BytesIO(response.read())).convert('RGB')
                image.thumbnail((150, 150))
                return pid, image
            self.task(image_work, self.show_image)

    def show_image(self, result):
        pid, image = result
        if self.product_tree.selection() != (str(pid),):
            return
        self.preview_image = ImageTk.PhotoImage(image)
        self.image_label.configure(image=self.preview_image)

    def add_catalog(self):
        selected = self.product_tree.selection()
        if selected and self.need_login():
            pid = int(selected[0])
            self.task(lambda: self.client.request('cart/', 'POST', {'product_id': pid, 'quantity': 1}), self.added)

    def added(self, result):
        self.load_cart()
        self.status.set('Товар добавлен в корзину')

    def ask_ai(self):
        if not self.need_login():
            return
        payload = {'preferences': self.preferences.get('1.0', 'end').strip(), 'budget': self.budget.get(), 'max_items': 3}
        if self.ai_faction.get() in self.factions:
            payload['faction'] = self.factions[self.ai_faction.get()]
        if CATEGORIES[self.ai_category.get()]:
            payload['product_type'] = CATEGORIES[self.ai_category.get()]
        self.task(lambda: self.client.request('recommendations/', 'POST', payload), self.ai_loaded)

    def ai_loaded(self, result):
        self.recommendations = {i['product']['id']: i for i in result['items']}
        self.recommend_tree.delete(*self.recommend_tree.get_children())
        for i in result['items']:
            self.recommend_tree.insert('', 'end', iid=str(i['product']['id']), values=(i['product']['name'], i['quantity'], money(i['total_price']), i['reason']))
        self.ai_explanation.set('Итого: ' + money(result['total_price']) + ' / Бюджет: ' + money(result['budget']) + '\n' + result['explanation'])

    def recommend_selected(self, event=None):
        selected = self.recommend_tree.selection()
        if selected:
            item = self.recommendations[int(selected[0])]
            self.ai_explanation.set(item['product']['name'] + '\n' + item['reason'])

    def add_recommendation(self):
        selected = self.recommend_tree.selection()
        if selected and self.need_login():
            item = self.recommendations[int(selected[0])]
            self.task(lambda: self.client.request('cart/', 'POST', {'product_id': item['product']['id'], 'quantity': item['quantity']}), self.added)

    def load_cart(self):
        if self.client.token:
            self.task(lambda: self.client.request('cart/'), self.cart_loaded)

    def cart_loaded(self, result):
        self.cart_items = {i['id']: i for i in result['items']}
        self.cart_tree.delete(*self.cart_tree.get_children())
        for i in result['items']:
            self.cart_tree.insert('', 'end', iid=str(i['id']), values=(i['product']['name'], i['quantity'], money(i['product']['discounted_price']), money(i['total_price'])))
        self.cart_total.set('Итого: ' + money(result['total_price']))

    def update_quantity(self):
        selected = self.cart_tree.selection()
        if not selected:
            return
        try:
            quantity = int(self.quantity.get())
        except ValueError:
            messagebox.showinfo('Количество', 'Введите целое положительное число.', parent=self)
            return
        path = 'cart/items/' + selected[0] + '/'
        self.task(lambda: self.client.request(path, 'PATCH', {'quantity': quantity}), lambda _: self.load_cart())

    def remove_item(self):
        selected = self.cart_tree.selection()
        if selected:
            path = 'cart/items/' + selected[0] + '/'
            self.task(lambda: self.client.request(path, 'DELETE'), lambda _: self.load_cart())

    def checkout(self):
        if not self.need_login():
            return
        if not messagebox.askyesno('Оформление', 'Оформить заказ из текущей корзины?', parent=self):
            return
        self.task(lambda: self.client.request('orders/', 'POST', {}), self.order_created)

    def order_created(self, result):
        self.load_cart()
        self.load_catalog()
        self.tabs.select(self.orders_tab)
        self.load_orders()
        messagebox.showinfo('Заказ оформлен', 'Номер вашего заказа: ' + str(result['id']), parent=self)

    def load_orders(self):
        if self.client.token:
            self.task(lambda: self.client.request('orders/'), self.orders_loaded)

    def orders_loaded(self, result):
        self.orders_tree.delete(*self.orders_tree.get_children())
        for o in result:
            items = '; '.join(i['product_name'] + ' × ' + str(i['quantity']) for i in o['items'])
            self.orders_tree.insert('', 'end', iid=str(o['id']), values=(o['id'], o['created_at'][:19].replace('T', ' '),
                money(o['total_price']), 'В обработке' if o['status'] == 'PROCESSING' else o['status'], items))

    def tab_changed(self, event=None):
        selected = self.tabs.select()
        if selected == str(self.cart_tab):
            self.load_cart()
        elif selected == str(self.orders_tab):
            self.load_orders()

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default=os.getenv('WARHAMMER_SERVER_URL', 'http://127.0.0.1:8000'))
    args = parser.parse_args()
    StoreApp(args.server).mainloop()
