"""Menu definition for the seeded restaurant: North Indian and Indo-Chinese, 45 items.

Prices and food costs are in whole rupees. `weight` is the relative chance an item is
picked when a guest chooses from its category. `drift` is the total change in that
weight across the seeded period (0.3 means 30 percent more popular by the last day).
"""
from __future__ import annotations

from dataclasses import dataclass, field

CATEGORIES: list[tuple[str, str]] = [
    ("Starters", "starter"),
    ("Mains", "main"),
    ("Breads", "bread"),
    ("Rice and Noodles", "rice"),
    ("Sides", "side"),
    ("Desserts", "dessert"),
    ("Beverages", "beverage"),
]


@dataclass(frozen=True)
class MenuItem:
    name: str
    category: str
    price: int
    food_cost: int
    veg: bool
    spice: int
    prep: int
    station: str
    weight: float
    tags: tuple[str, ...] = field(default_factory=tuple)
    drift: float = 0.0


# tags drive basket behaviour in the generator:
#   curry      eaten with bread or plain rice
#   paneer     can take the Extra Paneer add-on
#   biryani    pairs with raita, takes Extra Raita
#   chinese    Indo-Chinese, pairs with Manchurian and a cold drink
#   thali      a full meal, often followed by dessert
#   plain_rice side rice for a curry
#   snack      ordered in the evening snack window
#   sized      has a required Half / Full choice
M = MenuItem
MENU: list[MenuItem] = [
    # Starters
    M("Paneer Tikka", "starter", 260, 84, True, 2, 15, "tandoor", 18, ("paneer", "snack")),
    M("Chilli Paneer", "starter", 250, 76, True, 2, 12, "wok", 16, ("paneer", "snack")),
    M("Chicken Tikka", "starter", 320, 138, False, 2, 18, "tandoor", 36, ("snack",)),
    M("Tandoori Chicken", "starter", 380, 172, False, 2, 25, "tandoor", 45, ("sized",)),
    M("Veg Manchurian", "starter", 210, 62, True, 2, 12, "wok", 14, ("snack",)),
    M("Hara Bhara Kabab", "starter", 260, 66, True, 1, 15, "tandoor", 3.5, ("snack",)),
    M("Crispy Corn", "starter", 190, 82, True, 1, 10, "wok", 4, ("snack",)),
    # Mains
    M("Paneer Butter Masala", "main", 280, 98, True, 2, 15, "curry", 15, ("curry", "paneer")),
    M("Butter Chicken", "main", 360, 164, False, 2, 18, "curry", 24, ("curry",), drift=-0.15),
    M("Dal Makhani", "main", 240, 68, True, 1, 10, "curry", 14, ("curry",)),
    M("Kadai Paneer", "main", 290, 108, True, 3, 15, "curry", 8, ("curry", "paneer")),
    M("Paneer Tikka Masala", "main", 300, 116, True, 2, 15, "curry", 7, ("curry", "paneer"), drift=0.35),
    M("Veg Thali", "main", 300, 128, True, 2, 12, "curry", 8, ("thali",)),
    M("Chicken Curry", "main", 320, 148, False, 3, 18, "curry", 17, ("curry",)),
    M("Dal Tadka", "main", 190, 88, True, 2, 10, "curry", 13, ("curry",), drift=0.1),
    M("Chana Masala", "main", 200, 94, True, 2, 10, "curry", 9, ("curry",)),
    M("Malai Kofta", "main", 320, 104, True, 1, 18, "curry", 2.5, ("curry",)),
    M("Shahi Paneer", "main", 310, 104, True, 1, 15, "curry", 3, ("curry", "paneer")),
    M("Mix Veg", "main", 220, 104, True, 2, 12, "curry", 2.5, ("curry",)),
    # Breads
    M("Butter Naan", "bread", 60, 16, True, 0, 6, "tandoor", 27),
    M("Garlic Naan", "bread", 70, 20, True, 0, 6, "tandoor", 20),
    M("Lachha Paratha", "bread", 65, 19, True, 0, 7, "tandoor", 20),
    M("Tandoori Roti", "bread", 25, 8, True, 0, 4, "tandoor", 38),
    M("Cheese Naan", "bread", 110, 30, True, 0, 8, "tandoor", 5),
    # Rice and noodles
    M("Veg Biryani", "rice", 260, 108, True, 2, 20, "curry", 22, ("biryani",)),
    M("Chicken Biryani", "rice", 320, 150, False, 2, 25, "curry", 34, ("biryani",)),
    M("Hakka Noodles", "rice", 220, 68, True, 1, 12, "wok", 18, ("chinese",)),
    M("Veg Fried Rice", "rice", 210, 62, True, 1, 12, "wok", 18, ("chinese",)),
    M("Schezwan Noodles", "rice", 250, 72, True, 3, 12, "wok", 4, ("chinese",)),
    M("Steamed Rice", "rice", 130, 50, True, 0, 8, "curry", 17, ("plain_rice",)),
    M("Jeera Rice", "rice", 170, 72, True, 0, 10, "curry", 5, ("plain_rice",)),
    # Sides
    M("Boondi Raita", "side", 120, 30, True, 0, 3, "cold", 10),
    M("Green Salad", "side", 120, 34, True, 0, 4, "cold", 65),
    M("Masala Papad", "side", 60, 18, True, 1, 4, "tandoor", 25),
    # Desserts
    M("Gulab Jamun", "dessert", 130, 38, True, 0, 3, "dessert", 38),
    M("Gajar Halwa", "dessert", 140, 48, True, 0, 4, "dessert", 27),
    M("Sizzling Brownie", "dessert", 170, 78, True, 0, 8, "dessert", 27),
    M("Rasmalai", "dessert", 160, 46, True, 0, 3, "dessert", 6),
    M("Kulfi", "dessert", 80, 38, True, 0, 2, "dessert", 13),
    # Beverages
    M("Cold Drink", "beverage", 70, 33, True, 0, 1, "beverage", 12),
    M("Cold Coffee", "beverage", 150, 50, True, 0, 4, "beverage", 20, drift=0.3),
    M("Sweet Lassi", "beverage", 110, 30, True, 0, 3, "beverage", 19),
    M("Masala Chaas", "beverage", 110, 25, True, 0, 2, "beverage", 20),
    M("Fresh Lime Soda", "beverage", 110, 26, True, 0, 3, "beverage", 19),
    M("Mango Lassi", "beverage", 130, 40, True, 0, 3, "beverage", 18),
]

# Expected menu-engineering class for each item on the 30-day window. The seed tests
# check that the classifier finds these, so the patterns are discoverable, not random.
EXPECTED_CLASS: dict[str, str] = {
    "Veg Manchurian": "plowhorse", "Dal Tadka": "plowhorse", "Chana Masala": "plowhorse",
    "Tandoori Roti": "plowhorse", "Steamed Rice": "plowhorse", "Cold Drink": "plowhorse",
    "Hara Bhara Kabab": "puzzle", "Malai Kofta": "puzzle", "Shahi Paneer": "puzzle",
    "Cheese Naan": "puzzle", "Schezwan Noodles": "puzzle", "Rasmalai": "puzzle",
    "Crispy Corn": "dog", "Mix Veg": "dog", "Jeera Rice": "dog", "Masala Papad": "dog",
    "Kulfi": "dog",
}

# Modifier groups: (group name, required, min, max, [(modifier, price delta, cost delta)])
SPICE = ("Spice", False, 0, 1, [("Mild", 0, 0), ("Medium", 0, 0), ("Spicy", 0, 0)])


def modifier_groups_for(item: MenuItem) -> list[tuple]:
    groups: list[tuple] = []
    if "sized" in item.tags:
        half = -round(item.price * 0.45)
        half_cost = -round(item.food_cost * 0.5)
        groups.append(("Size", True, 1, 1, [("Full", 0, 0), ("Half", half, half_cost)]))
    if item.spice > 0 and item.category in ("starter", "main", "rice"):
        groups.append(SPICE)
    addons: list[tuple[str, int, int]] = []
    if "paneer" in item.tags and item.category == "main":
        addons.append(("Extra Paneer", 60, 30))
    if "biryani" in item.tags:
        addons += [("Extra Raita", 40, 12), ("Extra Salan", 30, 8)]
    if item.name == "Cold Coffee":
        addons.append(("Add Ice Cream", 40, 15))
    if item.name == "Butter Naan":
        addons.append(("Extra Butter", 10, 4))
    if addons:
        groups.append(("Add-ons", False, 0, len(addons), addons))
    return groups


# Optional inventory: ingredient -> (unit, stock, reorder level)
INGREDIENTS: dict[str, tuple[str, float, float]] = {
    "Paneer": ("kg", 22.0, 8.0),
    "Chicken": ("kg", 14.0, 10.0),
    "Black Urad Dal": ("kg", 12.0, 4.0),
    "Toor Dal": ("kg", 10.0, 4.0),
    "Chickpeas": ("kg", 8.0, 3.0),
    "Basmati Rice": ("kg", 40.0, 15.0),
    "Noodles": ("kg", 12.0, 5.0),
    "Maida": ("kg", 30.0, 10.0),
    "Atta": ("kg", 25.0, 8.0),
    "Butter": ("kg", 8.0, 3.0),
    "Cream": ("l", 3.5, 2.0),
    "Milk": ("l", 16.0, 10.0),
    "Curd": ("kg", 8.0, 5.0),
    "Mixed Vegetables": ("kg", 9.0, 6.0),
    "Cheese": ("kg", 4.0, 1.5),
    "Coffee": ("kg", 1.5, 0.5),
    "Mango Pulp": ("l", 1.5, 2.0),
}

# item -> [(ingredient, qty per plate)]
RECIPES: dict[str, list[tuple[str, float]]] = {
    "Paneer Tikka": [("Paneer", 0.18), ("Curd", 0.05)],
    "Chilli Paneer": [("Paneer", 0.16), ("Mixed Vegetables", 0.08)],
    "Chicken Tikka": [("Chicken", 0.25), ("Curd", 0.05)],
    "Tandoori Chicken": [("Chicken", 0.45), ("Curd", 0.06)],
    "Veg Manchurian": [("Mixed Vegetables", 0.2), ("Maida", 0.05)],
    "Hara Bhara Kabab": [("Mixed Vegetables", 0.2)],
    "Paneer Butter Masala": [("Paneer", 0.15), ("Butter", 0.03), ("Cream", 0.04)],
    "Butter Chicken": [("Chicken", 0.25), ("Butter", 0.04), ("Cream", 0.05)],
    "Dal Makhani": [("Black Urad Dal", 0.08), ("Butter", 0.03), ("Cream", 0.03)],
    "Kadai Paneer": [("Paneer", 0.16), ("Mixed Vegetables", 0.06)],
    "Paneer Tikka Masala": [("Paneer", 0.16), ("Cream", 0.03)],
    "Veg Thali": [("Toor Dal", 0.05), ("Basmati Rice", 0.1), ("Atta", 0.08), ("Paneer", 0.06)],
    "Chicken Curry": [("Chicken", 0.25)],
    "Dal Tadka": [("Toor Dal", 0.08)],
    "Chana Masala": [("Chickpeas", 0.1)],
    "Malai Kofta": [("Paneer", 0.1), ("Cream", 0.05)],
    "Shahi Paneer": [("Paneer", 0.15), ("Cream", 0.05)],
    "Mix Veg": [("Mixed Vegetables", 0.22)],
    "Butter Naan": [("Maida", 0.09), ("Butter", 0.01)],
    "Garlic Naan": [("Maida", 0.09), ("Butter", 0.01)],
    "Lachha Paratha": [("Atta", 0.09), ("Butter", 0.015)],
    "Tandoori Roti": [("Atta", 0.07)],
    "Cheese Naan": [("Maida", 0.09), ("Cheese", 0.04)],
    "Veg Biryani": [("Basmati Rice", 0.16), ("Mixed Vegetables", 0.08)],
    "Chicken Biryani": [("Basmati Rice", 0.16), ("Chicken", 0.2)],
    "Hakka Noodles": [("Noodles", 0.15), ("Mixed Vegetables", 0.06)],
    "Veg Fried Rice": [("Basmati Rice", 0.15), ("Mixed Vegetables", 0.06)],
    "Schezwan Noodles": [("Noodles", 0.15), ("Mixed Vegetables", 0.06)],
    "Steamed Rice": [("Basmati Rice", 0.15)],
    "Jeera Rice": [("Basmati Rice", 0.15)],
    "Boondi Raita": [("Curd", 0.12)],
    "Gajar Halwa": [("Milk", 0.1)],
    "Rasmalai": [("Milk", 0.2)],
    "Kulfi": [("Milk", 0.15)],
    "Cold Coffee": [("Milk", 0.25), ("Coffee", 0.01)],
    "Sweet Lassi": [("Curd", 0.25)],
    "Masala Chaas": [("Curd", 0.15)],
    "Mango Lassi": [("Curd", 0.2), ("Mango Pulp", 0.08)],
}


# One line per dish for the menu card and the Call desk, so staff can answer "what is it?" on the phone.
DESCRIPTIONS: dict[str, str] = {
    "Paneer Tikka": "Cottage cheese cubes marinated in spiced yoghurt, charred in the tandoor.",
    "Chilli Paneer": "Crisp paneer tossed with peppers, onion and green chilli in a soy glaze.",
    "Chicken Tikka": "Boneless chicken in yoghurt and Kashmiri chilli, cooked in the tandoor.",
    "Tandoori Chicken": "Half chicken on the bone, marinated overnight and roasted in the tandoor.",
    "Veg Manchurian": "Vegetable dumplings in a garlic, ginger and soy sauce.",
    "Hara Bhara Kabab": "Spinach, peas and potato patties, shallow fried.",
    "Crispy Corn": "Fried sweet corn tossed with pepper, onion and spice salt.",
    "Paneer Butter Masala": "Paneer in a smooth tomato, butter and cashew gravy.",
    "Butter Chicken": "Tandoori chicken simmered in a mild tomato and butter gravy.",
    "Dal Makhani": "Black lentils slow cooked overnight with butter and cream.",
    "Kadai Paneer": "Paneer with peppers and onion in a coarse kadai masala.",
    "Paneer Tikka Masala": "Tandoor-charred paneer in a spiced onion and tomato gravy.",
    "Veg Thali": "Dal, two vegetables, rice, two rotis, raita, salad and a sweet.",
    "Chicken Curry": "Home-style chicken on the bone in an onion and tomato gravy.",
    "Dal Tadka": "Yellow lentils tempered with cumin, garlic and red chilli.",
    "Chana Masala": "Chickpeas in a tangy onion, tomato and dry mango gravy.",
    "Malai Kofta": "Paneer and potato dumplings in a rich, mildly sweet cream gravy.",
    "Shahi Paneer": "Paneer in a creamy onion, cashew and cardamom gravy.",
    "Mix Veg": "Seasonal vegetables cooked dry with onion, tomato and spices.",
    "Butter Naan": "Leavened flour bread from the tandoor, brushed with butter.",
    "Garlic Naan": "Naan topped with chopped garlic and coriander.",
    "Lachha Paratha": "Layered whole-wheat flatbread, flaky and crisp.",
    "Tandoori Roti": "Whole-wheat flatbread baked in the tandoor.",
    "Cheese Naan": "Naan stuffed with melted cheese.",
    "Veg Biryani": "Basmati rice layered with vegetables, saffron and fried onion.",
    "Chicken Biryani": "Basmati rice dum-cooked with spiced chicken and saffron.",
    "Hakka Noodles": "Wok-tossed noodles with cabbage, carrot and spring onion.",
    "Veg Fried Rice": "Wok-fried rice with vegetables and soy.",
    "Schezwan Noodles": "Noodles tossed in a hot Schezwan chilli sauce.",
    "Steamed Rice": "Plain steamed basmati rice.",
    "Jeera Rice": "Basmati rice tempered with cumin and ghee.",
    "Boondi Raita": "Chilled yoghurt with crisp gram-flour pearls and roasted cumin.",
    "Green Salad": "Sliced onion, cucumber, tomato and lemon.",
    "Masala Papad": "Roasted papad topped with onion, tomato and chaat masala.",
    "Gulab Jamun": "Two warm milk dumplings in rose and cardamom syrup.",
    "Gajar Halwa": "Carrots slow cooked with milk, ghee and nuts.",
    "Sizzling Brownie": "Chocolate brownie with vanilla ice cream on a hot plate.",
    "Rasmalai": "Soft cheese patties in chilled saffron milk.",
    "Kulfi": "Dense Indian ice cream with pistachio and cardamom.",
    "Cold Drink": "Chilled soft drink, 300 ml.",
    "Cold Coffee": "Blended iced coffee with milk.",
    "Sweet Lassi": "Thick sweetened yoghurt drink.",
    "Masala Chaas": "Spiced buttermilk with roasted cumin and mint.",
    "Fresh Lime Soda": "Fresh lime with soda, sweet or salted.",
    "Mango Lassi": "Yoghurt blended with mango pulp.",
}


def photo_urls() -> dict[str, str]:
    """Dish name -> local photo URL ("/dishes/<slug>.webp"), for dishes whose photo was downloaded with
    `python -m seed.photos`. Credits for each photo are in the same folder (credits.json)."""
    import json
    from pathlib import Path

    folder = Path(__file__).resolve().parents[2] / "web" / "public" / "dishes"
    path = folder / "credits.json"
    if not path.exists():
        return {}
    credits = json.loads(path.read_text(encoding="utf-8"))
    return {name: c["file"] for name, c in credits.items() if (folder / Path(c["file"]).name).exists()}
