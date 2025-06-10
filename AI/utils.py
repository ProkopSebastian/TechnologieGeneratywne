import json

def recalculate_prices(parsed_json):
    def parse_price(value):
        try:
            return float(value.strip().replace(" PLN", "").replace(",", "."))
        except:
            return 0.0

    meals = parsed_json.get("meals", [])
    promo_cost = 0.0
    additional_cost = 0.0

    for meal in meals:
        for item in meal.get("main_products", []):
            promo_cost += parse_price(item.get("price", "0"))
        for item in meal.get("additional_ingredients", []):
            additional_cost += parse_price(item.get("price", item.get("estimated_price", "0")))

    total_cost = round(promo_cost + additional_cost, 2)

    # Update parsed_json to include correct totals
    parsed_json["plan_info"]["estimated_total_cost"] = f"{total_cost:.2f} PLN"
    parsed_json["shopping_summary"] = {
        "promotional_products_cost": f"{promo_cost:.2f} PLN",
        "additional_ingredients_cost": f"{additional_cost:.2f} PLN",
        "total_savings": parsed_json.get("shopping_summary", {}).get("total_savings", "0.00 PLN")  # preserve or override later
    }

    return {"raw_json": json.dumps(parsed_json, ensure_ascii=False)}


def recalculate_prices_manual(parsed_json):
    def parse_price(value):
        try:
            return float(value.strip().replace(" PLN", "").replace(",", "."))
        except:
            return 0.0

    meals = parsed_json.get("meals", [])
    promo_cost = 0.0
    additional_cost = 0.0

    for meal in meals:
        for item in meal.get("main_products", []):
            promo_cost += parse_price(item.get("price", "0"))
        for item in meal.get("additional_ingredients", []):
            additional_cost += parse_price(item.get("price", item.get("estimated_price", "0")))

    total_cost = round(promo_cost + additional_cost, 2)

    # Update the original structure
    parsed_json["plan_info"]["estimated_total_cost"] = f"{total_cost:.2f} PLN"
    parsed_json["shopping_summary"] = {
        "promotional_products_cost": f"{promo_cost:.2f} PLN",
        "additional_ingredients_cost": f"{additional_cost:.2f} PLN",
        "total_savings": parsed_json.get("shopping_summary", {}).get("total_savings", "0.00 PLN")  # Optional: override
    }

    return parsed_json