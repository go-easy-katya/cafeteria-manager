import re
from app import db, Dish, app

def parse_price(name_line):
    """Extract name and price from a line like 'ЛОБИО 130p' or 'ЛОБИО 130р'"""
    line = name_line.strip()
    # Match digits followed by p or р (Russian r)
    match = re.search(r'(\d+)\s*[pр]', line)
    if match:
        price = int(match.group(1))
        # Remove the price part to get the name
        name = re.sub(r'\s*\d+\s*[pр]', '', line).strip()
        return name, price
    return None, None

# Map possible category headers (with or without colon, case-insensitive)
category_map = {
    'ГАРНИРЫ': 'GARNISH',
    'ВТОРЫЕ БЛЮДА': 'MAIN',
    'СУПЫ': 'SOUP',
    'САЛАТЫ': 'SALAD',
}

def normalize_category(line):
    """Remove trailing colon and spaces, then check if it's a known category"""
    cleaned = line.strip().rstrip(':').strip()
    # Also remove any trailing spaces after colon
    return category_map.get(cleaned.upper())  # case-insensitive

def import_from_text_file(filename='dishes_list.txt'):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_category = None
    dishes_to_add = []
    skipped = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if this line is a category header
        cat = normalize_category(line)
        if cat:
            current_category = cat
            print(f"Found category: {cat}")
            continue
        
        # If we are in a category, try to parse dish
        if current_category:
            name, price = parse_price(line)
            if name and price:
                dishes_to_add.append({
                    'name_ru': name,
                    'name_en': '',
                    'category': current_category,
                    'default_price': price,
                    'is_active': True
                })
                print(f"Added: {name} - {price} ({current_category})")
            else:
                skipped += 1
                print(f"Skipped line: {line}")
    
    # Add dishes to database (skip duplicates)
    with app.app_context():
        added = 0
        for dish_data in dishes_to_add:
            existing = Dish.query.filter_by(name_ru=dish_data['name_ru']).first()
            if not existing:
                dish = Dish(**dish_data)
                db.session.add(dish)
                added += 1
            else:
                print(f"Duplicate skipped: {dish_data['name_ru']}")
        db.session.commit()
        print(f"\nAdded {added} new dishes. Total now: {Dish.query.count()}")
        print(f"Skipped {skipped} non-dish lines.")

if __name__ == '__main__':
    # Optional: clear all existing dishes? Only if you want to start fresh.
    # Uncomment the next lines if you want to delete all current dishes before import.
    # with app.app_context():
    #     db.session.query(Dish).delete()
    #     db.session.commit()
    #     print("Cleared existing dishes.")
    
    import_from_text_file()