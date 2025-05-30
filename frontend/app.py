import streamlit as st
import json
import requests
from typing import Dict, Any
import logging
import time
import sys

USE_MOCK = False
API_IRL="http://rag-backend:5000/api/ask"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


# mock json response
mock_response = {
    "meal": [
        {
            "day": 1,
            "name": "Scrambled Eggs",
            "content": "Fluffy scrambled eggs with herbs and butter.",
            "preparation": "Whisk eggs with salt and pepper, then cook in a buttered pan over medium heat while stirring.",
            "protein": 12,
            "carbohydrates": 2,
            "fats": 10,
            "ingredients": [
                {"name": "Jaja M", "quantity": "2 szt.", "description": "Świeże jajka rozmiar M"},
                {"name": "Masło extra", "quantity": "10g", "description": "Do smażenia"},
                {"name": "Sól i pieprz", "quantity": "szczypta", "description": "Przyprawy podstawowe"}
            ]
        },
        {
            "day": 1,
            "name": "Chicken Salad",
            "content": "Grilled chicken with lettuce, cherry tomatoes, and vinaigrette.",
            "preparation": "Grill chicken breast, slice, and toss with salad greens and dressing.",
            "protein": 30,
            "carbohydrates": 5,
            "fats": 8,
            "ingredients": [
                {"name": "Filet z kurczaka", "quantity": "200g", "description": "Mięso do grillowania"},
                {"name": "Sałata lodowa", "quantity": "100g", "description": "Świeża"},
                {"name": "Pomidorki koktajlowe", "quantity": "6 szt.", "description": "Do sałatki"},
                {"name": "Sos winegret", "quantity": "30ml", "description": "Gotowy dressing"}
            ]
        },
        {
            "day": 1,
            "name": "Spaghetti Bolognese",
            "content": "Classic Italian pasta with meat sauce.",
            "preparation": "Sauté onions and garlic, add minced beef and tomato sauce, simmer, then serve over cooked pasta.",
            "protein": 20,
            "carbohydrates": 45,
            "fats": 15,
            "ingredients": [
                {"name": "Makaron spaghetti", "quantity": "100g", "description": "Pełnoziarnisty"},
                {"name": "Mięso mielone wołowe", "quantity": "150g", "description": "Świeże lub mrożone"},
                {"name": "Passata pomidorowa", "quantity": "150ml", "description": "Do sosu"},
                {"name": "Czosnek", "quantity": "1 ząbek", "description": "Do podsmażenia"},
                {"name": "Cebula", "quantity": "1/2 szt.", "description": "Do podsmażenia"}
            ]
        }
    ],
    "shopping_list": [
        {"name": "Jaja M", "quantity": "2 szt.", "description": "Świeże jajka rozmiar M", "price": 1.80},
        {"name": "Masło extra", "quantity": "10g", "description": "Do smażenia", "price": 0.50},
        {"name": "Sól i pieprz", "quantity": "szczypta", "description": "Przyprawy podstawowe", "price": 0.10},
        {"name": "Filet z kurczaka", "quantity": "200g", "description": "Mięso do grillowania", "price": 6.50},
        {"name": "Sałata lodowa", "quantity": "100g", "description": "Świeża", "price": 2.00},
        {"name": "Pomidorki koktajlowe", "quantity": "6 szt.", "description": "Do sałatki", "price": 2.40},
        {"name": "Sos winegret", "quantity": "30ml", "description": "Gotowy dressing", "price": 1.20},
        {"name": "Makaron spaghetti", "quantity": "100g", "description": "Pełnoziarnisty", "price": 1.00},
        {"name": "Mięso mielone wołowe", "quantity": "150g", "description": "Świeże lub mrożone", "price": 5.00},
        {"name": "Passata pomidorowa", "quantity": "150ml", "description": "Do sosu", "price": 1.80},
        {"name": "Czosnek", "quantity": "1 ząbek", "description": "Do podsmażenia", "price": 0.40},
        {"name": "Cebula", "quantity": "1/2 szt.", "description": "Do podsmażenia", "price": 0.60}
    ],
    "status": "success"
}




# Mock function to simulate `requests.post(...)`
def mock_post(url: str, json: Dict[str, Any]):
    logger.info(f"Mock POST request to {url} with payload: {json}")

    class MockResponse:
        def __init__(self):
            self.status_code = 200

        def json(self):
            logger.info("Returning mock response JSON")
            time.sleep(1.0)
            return mock_response

    return MockResponse()

def post_query(query):
    if USE_MOCK:
        return mock_post("mock://diet", json={"query": query})
    else:
        return requests.post(API_IRL, json={"query": query})

def calculate_calories(p: int, c: int, f: int) -> int:
    return p * 4 + c * 4 + f * 9

def display_meals(meals):
    st.subheader("Oto przygotowany jadłospis dla Ciebie")

    meals_by_day = {}
    for meal in meals:
        meals_by_day.setdefault(meal["day"], []).append(meal)

    for day in sorted(meals_by_day):
        with st.expander(f"📅 Dzień {day}"):
            for meal in meals_by_day[day]:
                protein = meal.get("protein", 0)
                carbs = meal.get("carbohydrates", 0)
                fats = meal.get("fats", 0)
                calories = calculate_calories(protein, carbs, fats)

                st.markdown(f"### 🍽️ {meal['name']}")
                st.markdown(f"**Opis:** {meal['content']}")
                st.markdown(f"**Sposób przygotowania:** {meal.get('preparation', 'N/A')}")
                st.markdown(f"**Makroskładniki:** 🥩 {protein}g białka | 🍞 {carbs}g węglowodanów | 🧈 {fats}g tłuszczu")
                st.markdown(f"**Oszacowanie kaloryczne:** 🔥 **{calories} kcal**")
                
                if "ingredients" in meal:
                    st.markdown("**🛒 Składniki do zakupu:**")
                    for item in meal["ingredients"]:
                        st.write(f"- **{item['name']}** ({item['quantity']}): {item['description']}")
                st.markdown("---")

def display_shopping_list(items):
    st.subheader("🛒 Lista zakupów na cały jadłospis")

    total_price = 0.0
    for item in items:
        name = item["name"]
        qty = item["quantity"]
        desc = item["description"]
        price = item.get("price", 0.0)

        st.write(f"- **{name}** ({qty}): {desc} — {price:.2f} zł")
        total_price += price

    st.markdown("---")
    st.markdown(f"### 🧾 **Łączny koszt zakupów: {total_price:.2f} zł**")

st.set_page_config(page_title="Biedronka TEG", page_icon=None, layout="wide", initial_sidebar_state="auto", menu_items=None)
st.title("Inteligentne tworzenie diety z gazetki Biedronka")

# Initialize session state on first load
if "meals" not in st.session_state:
    st.session_state.meals = []
if "shopping_list" not in st.session_state:
    st.session_state.shopping_list = []
if "status" not in st.session_state:
    st.session_state.status = ""

query = st.text_input("Jak chcesz aby wyglądała twoja dieta", "Chcę dużo białka.")

if st.button("Stwórz jadłospis"):
    logger.info(f"Query submitted: {query}")
    with st.spinner("Pobieranie aktualnej gazetki i tworzenie jadłospisu..."):
        try:
            #response = requests.post("http://localhost:5000/api/ask", json={"query": query})
            response = post_query(query)

            if response.status_code != 200:
                logger.error(f"Server error: {response.status_code}")
                st.error("Błąd serwera.")
            else:
                result = response.json()
                if "meal" in result and "shopping_list" in result:
                    st.session_state.meals = result["meal"]
                    st.session_state.status = result["status"]

                    # handle status if added later
                    logger.info(f"Received {len(st.session_state.meals)} meals with status: {st.session_state.status}")
                    #logger.info(f"Received JSON {result}")

                    col1, col2 = st.columns([2, 1])

                    with col1:
                        display_meals(st.session_state.meals)

                    with col2:
                        display_shopping_list(result["shopping_list"])
                else:
                    logger.exception("no meal key in JSON recived")
                    st.error("Brak danych w odpowiedzi")
                    logger.info(f'Data: {result}')

        except Exception as e:
            logger.exception("Unhandled exception during diet generation")
            st.error(f'Błąd serwera: {str(e)}')

