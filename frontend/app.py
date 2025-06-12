import streamlit as st
import json
import requests
from typing import Dict, Any
import logging
import time
import sys
import os

API_URL = os.environ.get("API_URL", "http://rag-backend:5000/api/ask")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def post_query(query, days=1, people=1, dietary_restrictions=[], meal_types=[], excluded_ingredients=""):
    payload = {
        "query": query,
        "days": days,
        "people": people,
        "restrictions": dietary_restrictions,
        "meal_types": meal_types,
        "excluded_ingredients": excluded_ingredients,
    }

    return requests.post(API_URL, json=payload)

def get_meal_type_emoji(meal_type: str) -> str:
    """Get emoji for meal type"""
    emojis = {
        "breakfast": "🌅",
        "lunch": "☀️",
        "dinner": "🌙",
        "snack": "🍎"
    }
    return emojis.get(meal_type.lower(), "🍽️")

def display_meals(meals, plan_info):
    st.subheader("🍽️ Oto przygotowany jadłospis dla Ciebie")

    # Display plan info
    if plan_info:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👥 Liczba osób", plan_info.get("people", 1))
        with col2:
            st.metric("📅 Liczba dni", plan_info.get("days", 1))
        with col3:
            st.metric("💰 Szacowany koszt", plan_info.get("estimated_total_cost", "N/A"))

    st.markdown("---")

    # Group meals by day
    meals_by_day = {}
    for meal in meals:
        day = meal.get("day", 1)
        meals_by_day.setdefault(day, []).append(meal)

    # Display meals by day
    for day in sorted(meals_by_day.keys()):
        with st.expander(f"📅 Dzień {day}", expanded=True):
            day_meals = meals_by_day[day]

            # Sort meals by typical order (breakfast, lunch, dinner)
            meal_order = {"breakfast": 1, "lunch": 2, "dinner": 3, "snack": 4}
            day_meals.sort(key=lambda x: meal_order.get(x.get("type", "").lower(), 5))

            for meal in day_meals:
                meal_type = meal.get("type", "posiłek")
                meal_emoji = get_meal_type_emoji(meal_type)

                st.markdown(f"### {meal_emoji} {meal.get('name', 'Posiłek bez nazwy')}")
                # Display image if available
                #if meal.get('image_name'):
                #    st.image(f"Images/{meal['image_name']}.jpg", caption=meal.get('name', 'Posiłek bez nazwy'), use_container_width=True)

                st.markdown(f"**Typ:** {meal_type.title()}")
                st.markdown(f"**⏰ Czas przygotowania:** {meal.get('prep_time', 'N/A')}")
                st.markdown(f"**🍽️ Opis:** {meal.get('instructions', 'Brak opisu')}")

                # Main products from promotions
                main_products = meal.get("main_products", [])
                if main_products:
                    st.markdown("**🏷️ Produkty promocyjne z Biedronki:**")
                    for product in main_products:
                        product_info = f"- 🛒 **{product['name']}**"
                        if 'quantity' in product:
                            product_info += f" ({product['quantity']})"
                        if 'price' in product:
                            product_info += f" - {product['price']}"
                        st.write(product_info)

                # Additional ingredients
                additional_ingredients = meal.get("additional_ingredients", [])
                if additional_ingredients:
                    st.markdown("**🧂 Dodatkowe składniki:**")
                    for ingredient in additional_ingredients:
                        ingredient_info = f"- {ingredient['name']}"
                        if 'quantity' in ingredient:
                            ingredient_info += f" ({ingredient['quantity']})"
                        if 'estimated_price' in ingredient:
                            ingredient_info += f" - ~{ingredient['estimated_price']}"
                        st.write(ingredient_info)

                    st.markdown("---")


def display_shopping_summary(shopping_summary, meals):
    st.subheader("🛍️ Podsumowanie zakupów")

    # Zbierz wszystkie produkty i składniki
    all_main_products = set()
    all_additional_ingredients = set()

    for meal in meals:
        for product in meal.get("main_products", []):
            product_str = product['name']
            if 'quantity' in product:
                product_str += f" ({product['quantity']})"
            all_main_products.add(product_str)

        for ingredient in meal.get("additional_ingredients", []):
            ingredient_str = ingredient['name']
            if 'quantity' in ingredient:
                ingredient_str += f" ({ingredient['quantity']})"
            all_additional_ingredients.add(ingredient_str)

    # Wyświetl produkty promocyjne
    if all_main_products:
        st.markdown("**🏷️ Produkty promocyjne do kupienia w Biedronce:**")
        for product in sorted(all_main_products):
            st.write(f"- {product}")

    # Wyświetl dodatkowe składniki
    if all_additional_ingredients:
        st.markdown("**🧂 Inne potrzebne składniki:**")
        for ingredient in sorted(all_additional_ingredients):
            st.write(f"- {ingredient}")

    # Wyświetl podsumowanie kosztów
    if shopping_summary:
        st.markdown("**💰 Podsumowanie kosztów:**")
        if 'promotional_products_cost' in shopping_summary:
            st.write(f"- Koszt produktów promocyjnych: {shopping_summary['promotional_products_cost']}")
        if 'additional_ingredients_cost' in shopping_summary:
            st.write(f"- Koszt dodatkowych składników: {shopping_summary['additional_ingredients_cost']}")
        if 'total_savings' in shopping_summary:
            st.write(f"- Oszczędności dzięki promocjom: {shopping_summary['total_savings']}")
        if 'estimated_total_cost' in shopping_summary:
            st.write(f"- **Łączny szacowany koszt: {shopping_summary['estimated_total_cost']}**")

def display_error_message(result):
    """Display error message from API response"""
    st.error("❌ Nie udało się wygenerować jadłospisu")

    error_message = result.get("message", "Nieznany błąd")
    st.write(f"**Szczegóły błędu:** {error_message}")

    # Show raw response for debugging if available
    if "raw" in result:
        with st.expander("🔍 Szczegóły techniczne (dla debugowania)"):
            st.code(result["raw"])

# Streamlit configuration
st.set_page_config(
    page_title="Biedronka TEG",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="auto"
)

st.title("🛒 Inteligentne tworzenie diety z gazetki Biedronka")
st.markdown("Stwórz spersonalizowany jadłospis wykorzystując aktualne promocje!")

# Sidebar for parameters
with st.sidebar:
    st.header("⚙️ Ustawienia jadłospisu")

    days = st.slider("📅 Liczba dni", min_value=1, max_value=7, value=1, help="Na ile dni wygenerować jadłospis")
    people = st.slider("👥 Liczba osób", min_value=1, max_value=6, value=1, help="Dla ilu osób przygotować jadłospis")

    st.markdown("---")

    dietary_restrictions = st.multiselect(
        "🚫 Ograniczenia dietetyczne",
        ["Bezglutenowe", "Wegetariańskie", "Bez laktozy", "Keto"],
        help="Wybierz ograniczenia dietetyczne"
    )

    meal_types = st.multiselect(
        "🍽️ Rodzaje posiłków",
        ["śniadanie", "obiad", "kolacja", "przekąska"],
        default=["śniadanie", "obiad", "kolacja"]
    )

    excluded_ingredients = st.text_input(
        "❌ Składniki do unikania",
        placeholder="np. cebula, grzyby, orzechy"
    )


    st.markdown("---")
    st.markdown("**💡 Przykładowe zapytania:**")
    st.markdown("- Chcę dużo białka")
    st.markdown("- Dieta wegetariańska")
    st.markdown("- Szybkie posiłki do pracy")
    st.markdown("- Zdrowe przekąski dla dzieci")

# Initialize session state
if "meals" not in st.session_state:
    st.session_state.meals = []
if "plan_info" not in st.session_state:
    st.session_state.plan_info = {}
if "shopping_summary" not in st.session_state:
    st.session_state.shopping_summary = {}
if "status" not in st.session_state:
    st.session_state.status = ""

# Main input
query = st.text_input(
    "💭 Opisz swoje preferencje żywieniowe",
    placeholder="np. Chcę dużo białka i szybkie posiłki...",
    help="Opisz jakie posiłki Cię interesują - algorytm dobierze odpowiednie produkty z aktualnych promocji Biedronki"
)

# Generate meal plan button
if st.button("🎯 Stwórz jadłospis", type="primary"):
    if not query.strip():
        st.warning("⚠️ Proszę opisać swoje preferencje żywieniowe")
    else:
        logger.info(f"Query submitted: {query} (days={days}, people={people}, dietary_restrictions={dietary_restrictions}, meal_types={meal_types}, excluded_ingredients={excluded_ingredients})")

        with st.spinner("🔍 Pobieranie aktualnej gazetki i tworzenie jadłospisu..."):
            try:
                response = post_query(query, days, people, dietary_restrictions, meal_types, excluded_ingredients)

                if response.status_code != 200:
                    logger.error(f"Server error: {response.status_code}")
                    st.error(f"❌ Błąd serwera: {response.status_code}")
                else:
                    result = response.json()
                    logger.info(f"Received response with status: {result.get('status', 'unknown')}")

                    if result.get("status") == "success":
                        # Store results in session state
                        st.session_state.meals = result.get("meals", [])
                        st.session_state.plan_info = result.get("plan_info", {})
                        st.session_state.shopping_summary = result.get("shopping_summary", {})
                        st.session_state.status = result["status"]

                        logger.info(f"Successfully loaded {len(st.session_state.meals)} meals")

                        # Display success
                        st.success("✅ Jadłospis został pomyślnie wygenerowany!")

                    else:
                        # Handle error response
                        display_error_message(result)

            except requests.exceptions.RequestException as e:
                logger.exception("Network error during diet generation")
                st.error(f"❌ Błąd połączenia z serwerem: {str(e)}")
            except json.JSONDecodeError as e:
                logger.exception("JSON decode error")
                st.error("❌ Błąd w odpowiedzi serwera - nieprawidłowy format danych")
            except Exception as e:
                logger.exception("Unhandled exception during diet generation")
                st.error(f"❌ Nieoczekiwany błąd: {str(e)}")

# Display results if available
if st.session_state.status == "success" and st.session_state.meals:
    st.markdown("---")

    # Create two columns for layout
    col1, col2 = st.columns([2, 1])

    with col1:
        display_meals(st.session_state.meals, st.session_state.plan_info)

    with col2:
        display_shopping_summary(st.session_state.shopping_summary, st.session_state.meals)

# Footer
st.markdown("---")
st.markdown("🤖 **Powered by AI** | Jadłospis generowany na podstawie aktualnych promocji w Biedronka")
