from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import and_
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafe.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-change-this-to-something-random'  # ← change this!

db = SQLAlchemy(app)

# Category choices
CATEGORIES = [
    ('SALAD', 'Салат'),
    ('SOUP', 'Суп'),
    ('MAIN', 'Второе блюдо'),
    ('GARNISH', 'Гарнир'),
    ('DRINK', 'Напиток'),
    ('OTHER', 'Прочее')
]

CATEGORY_RU = {
    'SALAD': 'САЛАТЫ',
    'SOUP': 'СУПЫ',
    'MAIN': 'ВТОРЫЕ БЛЮДА',
    'GARNISH': 'ГАРНИРЫ',
    'DRINK': 'НАПИТКИ',
    'OTHER': 'ПРОЧЕЕ'
}

# Models
class Dish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name_ru = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100))
    category = db.Column(db.String(20), nullable=False)
    default_price = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class DailyMenu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    items = db.relationship('MenuItem', backref='daily_menu', cascade='all, delete-orphan')

class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    daily_menu_id = db.Column(db.Integer, db.ForeignKey('daily_menu.id'), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey('dish.id'), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    price_rub = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Integer, default=0)
    dish = db.relationship('Dish')

class ComplexLunchItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('complex_lunch_menu.id'), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    name_ru = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100))
    position = db.Column(db.Integer, default=0)

class ComplexLunchMenu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    fixed_price = db.Column(db.Integer, default=420)

    @property
    def first_courses(self):
        return ComplexLunchItem.query.filter_by(menu_id=self.id, category='first').order_by(ComplexLunchItem.position).all()
    @property
    def second_courses(self):
        return ComplexLunchItem.query.filter_by(menu_id=self.id, category='second').order_by(ComplexLunchItem.position).all()
    @property
    def garnishes(self):
        return ComplexLunchItem.query.filter_by(menu_id=self.id, category='garnish').order_by(ComplexLunchItem.position).all()
    @property
    def salads(self):
        return ComplexLunchItem.query.filter_by(menu_id=self.id, category='salad').order_by(ComplexLunchItem.position).all()
    @property
    def drinks(self):
        return ComplexLunchItem.query.filter_by(menu_id=self.id, category='drink').order_by(ComplexLunchItem.position).all()

with app.app_context():
    db.create_all()


# --- Flask-Login User Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

# CHANGE THIS PASSWORD!
ADMIN_USERNAME = 'bananaleaf'
ADMIN_PASSWORD = 'bananaleaf9c2'

users_by_id = {}
users_by_name = {}
admin_user = User(id=1, username=ADMIN_USERNAME, password_hash=generate_password_hash(ADMIN_PASSWORD))
users_by_id[admin_user.id] = admin_user
users_by_name[admin_user.username] = admin_user
WORKER_USERNAME = 'satish'
WORKER_PASSWORD = 'satish9c2'
worker_user = User(id=2, username=WORKER_USERNAME, password_hash=generate_password_hash(WORKER_PASSWORD))
users_by_id[worker_user.id] = worker_user
users_by_name[worker_user.username] = worker_user
class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    content = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(80), default=ADMIN_USERNAME)

    def __repr__(self):
        return f'<Note {self.date} - {self.content[:20]}>'

@login_manager.user_loader
def load_user(user_id):
    return users_by_id.get(int(user_id))
def is_admin():
    return current_user.is_authenticated and current_user.username == ADMIN_USERNAME

# Login & Logout routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = users_by_name.get(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------- Helper: check if admin ----------
def is_admin():
    return current_user.is_authenticated and current_user.username == ADMIN_USERNAME

# ---------- Notes routes (admin only) ----------
@app.route('/notes')
@login_required
def notes_list():
    # Allow both admin and worker to view, but controls will be hidden for worker
    all_notes = Note.query.order_by(Note.date.desc()).all()
    notes_by_date = {}
    for note in all_notes:
        notes_by_date[note.date] = note
    return render_template('notes.html', 
                           notes_by_date=notes_by_date, 
                           today=date.today(),
                           is_admin=(current_user.username == ADMIN_USERNAME))

@app.route('/notes/date/<date_str>', methods=['GET', 'POST'])
@login_required
def notes_by_date(date_str):
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return "Invalid date format", 400

    note = Note.query.filter_by(date=target_date).first()
    is_admin_user = (current_user.username == ADMIN_USERNAME)

    if request.method == 'POST':
        if not is_admin_user:
            return "Access denied. Only admin can edit notes.", 403
        content = request.form.get('content', '').strip()
        if content:
            if note:
                note.content = content
            else:
                note = Note(date=target_date, content=content, created_by=current_user.username)
                db.session.add(note)
            db.session.commit()
            return redirect(url_for('notes_by_date', date_str=date_str))
        else:
            # if empty content, ignore
            pass

    # For GET request or after POST redirect, show the note (read-only if worker)
    return render_template('note_form.html', 
                           date=target_date, 
                           note=note,
                           is_admin=is_admin_user)


@app.route('/notes/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    if current_user.username != ADMIN_USERNAME:
        return "Access denied. Only admin can edit notes.", 403
    note = Note.query.get_or_404(note_id)
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            note.content = content
            db.session.commit()
        return redirect(url_for('notes_by_date', date_str=note.date.isoformat()))
    return render_template('note_form.html', 
                           date=note.date, 
                           note=note,
                           is_admin=True)

@app.route('/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    if current_user.username != ADMIN_USERNAME:
        return "Access denied. Only admin can delete notes.", 403
    note = Note.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('notes_list'))

@app.route('/notes/search', methods=['GET'])
@login_required
def search_notes():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('notes_list'))
    results = Note.query.filter(Note.content.contains(query)).order_by(Note.date.desc()).all()
    return render_template('notes_search.html', 
                           results=results, 
                           query=query,
                           is_admin=(current_user.username == ADMIN_USERNAME))

# Helper functions
def get_or_create_today_menu():
    today = date.today()
    daily_menu = DailyMenu.query.filter_by(date=today).first()
    if not daily_menu:
        daily_menu = DailyMenu(date=today)
        db.session.add(daily_menu)
        db.session.commit()
    return daily_menu

def get_or_create_today_complex():
    today = date.today()
    complex_menu = ComplexLunchMenu.query.filter_by(date=today).first()
    if not complex_menu:
        complex_menu = ComplexLunchMenu(date=today, fixed_price=420)
        db.session.add(complex_menu)
        db.session.commit()
    return complex_menu

# ---------- PROTECTED ROUTES (all require login) ----------
@app.route('/')
@login_required
def dashboard():
    today = date.today()
    today_menu = DailyMenu.query.filter_by(date=today).first()
    today_count = len(today_menu.items) if today_menu else 0
    recent_menus = DailyMenu.query.order_by(DailyMenu.date.desc()).limit(10).all()
    return render_template('dashboard.html', today=today, today_count=today_count, recent_menus=recent_menus)

@app.route('/dishes', methods=['GET', 'POST'])
@login_required
def dishes():
    if request.method == 'POST':
        name_ru = request.form.get('name_ru')
        name_en = request.form.get('name_en')
        category = request.form.get('category')
        default_price = request.form.get('default_price')
        if name_ru and category and default_price:
            dish = Dish(
                name_ru=name_ru,
                name_en=name_en or '',
                category=category,
                default_price=int(default_price),
                is_active=True
            )
            db.session.add(dish)
            db.session.commit()
    all_dishes = Dish.query.order_by(Dish.category, Dish.name_ru).all()
    return render_template('dishes.html', dishes=all_dishes, categories=CATEGORIES)

@app.route('/dishes/<int:dish_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    if request.method == 'POST':
        dish.name_ru = request.form.get('name_ru')
        dish.name_en = request.form.get('name_en')
        dish.category = request.form.get('category')
        dish.default_price = int(request.form.get('default_price'))
        dish.is_active = 'is_active' in request.form
        db.session.commit()
        return redirect(url_for('dishes'))
    return render_template('edit_dish.html', dish=dish, categories=CATEGORIES)
@app.route('/dishes/<int:dish_id>/delete', methods=['POST'])
@login_required
def delete_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    # Check if dish is used in any menu items
    used_in_menus = MenuItem.query.filter_by(dish_id=dish_id).first()
    if used_in_menus:
        # Instead of deleting, you could mark as inactive, but here we'll warn
        return "Cannot delete dish because it appears in some menus. You can edit it and set 'Active' to false instead.", 400
    db.session.delete(dish)
    db.session.commit()
    return redirect(url_for('dishes'))

@app.route('/menu/today', methods=['GET', 'POST'])
@login_required
def edit_today_menu():
    today = date.today()
    daily_menu = get_or_create_today_menu()
    all_dishes = Dish.query.filter_by(is_active=True).order_by(Dish.category, Dish.name_ru).all()
    current_items = {item.dish_id: item for item in daily_menu.items}
    if request.method == 'POST':
        for item in daily_menu.items:
            db.session.delete(item)
        for dish in all_dishes:
            checkbox_key = f'dish_{dish.id}'
            if checkbox_key in request.form:
                price_key = f'price_{dish.id}'
                price = request.form.get(price_key, dish.default_price)
                menu_item = MenuItem(
                    daily_menu_id=daily_menu.id,
                    dish_id=dish.id,
                    category=dish.category,
                    price_rub=int(price),
                    position=0
                )
                db.session.add(menu_item)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('edit_menu.html', daily_menu=daily_menu, dishes=all_dishes, current_items=current_items, categories=CATEGORIES)

@app.route('/menu/<date>/print-main')
@login_required
def print_menu(date):
    try:
        menu_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD", 400
    daily_menu = DailyMenu.query.filter_by(date=menu_date).first()
    if not daily_menu:
        return f"No menu found for {date}", 404
    items_by_category = {}
    for item in daily_menu.items:
        cat = item.category
        if cat not in items_by_category:
            items_by_category[cat] = []
        items_by_category[cat].append(item)
    for cat in items_by_category:
        items_by_category[cat].sort(key=lambda x: x.dish.name_ru)
    return render_template('print_main.html', date=menu_date, items_by_category=items_by_category, category_ru=CATEGORY_RU)

@app.route('/stats')
@login_required
def stats():
    from sqlalchemy import func
    dish_counts = db.session.query(
        Dish.id, Dish.name_ru, Dish.name_en, func.count(MenuItem.id).label('menu_count')
    ).outerjoin(MenuItem, Dish.id == MenuItem.dish_id).group_by(Dish.id).order_by(func.count(MenuItem.id).desc()).all()
    return render_template('stats.html', dish_counts=dish_counts)

@app.route('/dish/<int:dish_id>/price-history')
@login_required
def price_history(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    history = db.session.query(MenuItem, DailyMenu).join(DailyMenu).filter(MenuItem.dish_id == dish_id).order_by(DailyMenu.date.desc()).all()
    return render_template('price_history.html', dish=dish, history=history)

# ─────────────────────────────────────────────────────────────────────────────
#  FIXED: Redirect today's complex lunch to the date‑specific editor
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/complex/today', methods=['GET', 'POST'])
@login_required
def edit_complex_today():
    # Redirect to the date‑specific editor using today's date
    today_str = date.today().isoformat()  # YYYY-MM-DD
    return redirect(url_for('edit_complex_by_date', date=today_str))
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/complex/<date>/print')
@login_required
def print_complex(date):
    try:
        menu_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD", 400
    complex_menu = ComplexLunchMenu.query.filter_by(date=menu_date).first()
    if not complex_menu:
        return f"No complex lunch found for {date}", 404
    items_by_category = {
        'first': complex_menu.first_courses,
        'second': complex_menu.second_courses,
        'garnish': complex_menu.garnishes,
        'salad': complex_menu.salads,
        'drink': complex_menu.drinks,
    }
    return render_template('print_complex.html', date=menu_date, items_by_category=items_by_category, fixed_price=complex_menu.fixed_price)

@app.route('/menu/<date>/edit', methods=['GET', 'POST'])
@login_required
def edit_menu_by_date(date):
    try:
        menu_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD", 400
    daily_menu = DailyMenu.query.filter_by(date=menu_date).first()
    if not daily_menu:
        daily_menu = DailyMenu(date=menu_date)
        db.session.add(daily_menu)
        db.session.commit()
    all_dishes = Dish.query.filter_by(is_active=True).order_by(Dish.category, Dish.name_ru).all()
    current_items = {item.dish_id: item for item in daily_menu.items}
    if request.method == 'POST':
        for item in daily_menu.items:
            db.session.delete(item)
        for dish in all_dishes:
            checkbox_key = f'dish_{dish.id}'
            if checkbox_key in request.form:
                price_key = f'price_{dish.id}'
                price = request.form.get(price_key, dish.default_price)
                menu_item = MenuItem(
                    daily_menu_id=daily_menu.id,
                    dish_id=dish.id,
                    category=dish.category,
                    price_rub=int(price),
                    position=0
                )
                db.session.add(menu_item)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('edit_menu_by_date.html', daily_menu=daily_menu, dishes=all_dishes, current_items=current_items, categories=CATEGORIES)

@app.route('/complex/<date>/edit', methods=['GET', 'POST'])
@login_required
def edit_complex_by_date(date):
    try:
        menu_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD", 400

    # Get or create the ComplexLunchMenu for that date
    complex_menu = ComplexLunchMenu.query.filter_by(date=menu_date).first()
    if not complex_menu:
        complex_menu = ComplexLunchMenu(date=menu_date, fixed_price=420)
        db.session.add(complex_menu)
        db.session.commit()

    # Get the regular menu for this date (to provide dropdown choices)
    daily_menu = DailyMenu.query.filter_by(date=menu_date).first()
    regular_dishes_by_category = {
        'first': [],    # SOUP
        'second': [],   # MAIN
        'garnish': [],  # GARNISH
        'salad': [],    # SALAD
        'drink': []     # DRINK
    }
    if daily_menu:
        for item in daily_menu.items:
            if item.category == 'SOUP':
                regular_dishes_by_category['first'].append(item.dish.name_ru)
            elif item.category == 'MAIN':
                regular_dishes_by_category['second'].append(item.dish.name_ru)
            elif item.category == 'GARNISH':
                regular_dishes_by_category['garnish'].append(item.dish.name_ru)
            elif item.category == 'SALAD':
                regular_dishes_by_category['salad'].append(item.dish.name_ru)
            elif item.category == 'DRINK':
                regular_dishes_by_category['drink'].append(item.dish.name_ru)
    # Remove duplicates and sort
    for cat in regular_dishes_by_category:
        regular_dishes_by_category[cat] = sorted(set(regular_dishes_by_category[cat]))

    # Current complex lunch items
    current_items = {
        'first': [item.name_ru for item in complex_menu.first_courses],
        'second': [item.name_ru for item in complex_menu.second_courses],
        'garnish': [item.name_ru for item in complex_menu.garnishes],
        'salad': [item.name_ru for item in complex_menu.salads],
        'drink': [item.name_ru for item in complex_menu.drinks],
    }

    if request.method == 'POST':
        # Clear existing complex items
        ComplexLunchItem.query.filter_by(menu_id=complex_menu.id).delete()

        # Process each category
        for category in ['first', 'second', 'garnish', 'salad', 'drink']:
            # Get selected items from dropdowns (list of names)
            selected_items = request.form.getlist(f'{category}_select')
            # Get custom typed items
            custom_items = request.form.getlist(f'{category}_custom')
            # Combine, filter empty, trim spaces
            all_items = [name.strip() for name in selected_items + custom_items if name.strip()]
            # Remove duplicates while preserving order
            unique_items = []
            for name in all_items:
                if name not in unique_items:
                    unique_items.append(name)
            # Save each as a ComplexLunchItem
            for i, name in enumerate(unique_items):
                item = ComplexLunchItem(
                    menu_id=complex_menu.id,
                    category=category,
                    name_ru=name,
                    name_en='',
                    position=i
                )
                db.session.add(item)

        complex_menu.fixed_price = int(request.form.get('fixed_price', 420))
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template('edit_complex_by_date.html',
                         complex_menu=complex_menu,
                         regular_dishes=regular_dishes_by_category,
                         current_items=current_items)

if __name__ == '__main__':
    app.run(debug=True)