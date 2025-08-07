# utils.py

from config import DISCOUNT_THRESHOLD, DISCOUNT_PERCENTAGE

def calculate_price(page_count):
    price_per_page = 2  # ₹2 per page for black & white only
    total = page_count * price_per_page

    if total >= DISCOUNT_THRESHOLD:
        discount = (DISCOUNT_PERCENTAGE / 100) * total
        total -= discount

    return round(total, 2)

def parse_room_number(room_text):
    try:
        room_number = int(room_text)
        floor = int(str(room_number)[:len(str(room_number)) - 2])  # works for 101, 1101, etc.
        return floor, room_number
    except:
        return None, None
