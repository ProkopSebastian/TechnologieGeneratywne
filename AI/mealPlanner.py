import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import openai
import pickle
from typing import List, Dict, Any, Optional
import os
from logger import get_logger
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import pandas as pd
from uuid import uuid4
from qdrant_client.models import VectorParams, Distance, PointStruct
from qdrant_client.http.models import SearchRequest
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableLambda, RunnableSequence
import openai
from langsmith import traceable
from prompts import search_query_prompt, translation_prompt, generic_translation_prompt, chat_prompt, recalculate_prompt
from utils import recalculate_prices, recalculate_prices_manual

class MealPlannerAPI:
    def __init__(self):
        self.API_KEY = os.getenv('OPENAI_API_KEY')
        self.QDRANT_HOST = os.getenv('QDRANT_HOST', 'qdrant')
        self.RECIPE_DATA_PATH = "shared_data/recipe_embeddings.pkl"
        self.PRODUCTS_FILE = "shared_data/biedronka_offers_enhanced.json"

        self.client = openai.OpenAI(api_key=self.API_KEY)
        self.logger = get_logger("app-MealPlanner")

        self.qdrant_client = QdrantClient(host=self.QDRANT_HOST, port=6333)
        self.embedding_model = OpenAIEmbeddings(openai_api_key=self.API_KEY)

        self.llm_quick = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0,
            max_tokens=60
        )

        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=6000
        )

        self.str_parser = StrOutputParser()
        self.json_parser = JsonOutputParser()

        # chains
        self.search_query_chain = search_query_prompt | self.llm_quick | self.str_parser
        self.translation_chain = translation_prompt | self.llm_quick | self.str_parser
        self.generic_translation_chain = generic_translation_prompt | self.llm_quick | self.str_parser

        self.chat_chain = chat_prompt | self.llm | self.json_parser
        # self.chat_chain: RunnableSequence = (
        #     chat_prompt
        #     | self.llm
        #     | self.json_parser  # returns dict
        #     | RunnableLambda(recalculate_prices)
        #     | recalculate_prompt
        #     | self.llm
        #     | self.json_parser  # final parsed dict
        # )

        # Load data
        self._load_data()
        # translate products to english for better results
        self.translate_product_names()

    def translate_product_names(self):
        """Translate Polish product names into English (once per session)."""
        for product in self.products:
            original_name = product.get("name", "")
            try:
                # Skip if already translated
                if "translated_name" in product:
                    continue

                translated = self.translation_chain.invoke({"product_name": original_name})

                product["translated_name"] = translated
                self.logger.info(f"🗨️ Translated: {original_name} → {translated}")

            except Exception as e:
                self.logger.error(f"❌ Translation failed for '{original_name}': {e}")
                product["translated_name"] = original_name  # fallback

    def _load_data(self):
        """Load recipe embeddings and product data"""
        try:
            # Load products
            with open(self.PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                products_data = json.load(f)

            self.products = products_data['products']
            self.logger.info(f"Loaded {len(self.products)} products from Biedronka")

        except Exception as e:
            self.logger.error(f"Error loading data: {e}")
            raise

    def translate_to_english(self, text: str) -> str:
        try:
            return self.generic_translation_chain.invoke({"input_text": text})
        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            return text  # fallback to original if translation fails

    def generate_search_query(self, user_query: str) -> str:
        """
        Convert user query into a concise recipe search query using LangChain.
        """
        try:
            rewritten = self.search_query_chain.invoke({"user_request": user_query})
            # result = self.search_query_chain.run(user_request=user_query)
            # rewritten = result.strip()
            self.logger.info(f"Rewritten query: {rewritten}")
            return rewritten
        except Exception as e:
            self.logger.error(f"LangChain search query generation failed: {e}")
            return user_query

    @traceable(name="batch_search_recipes")
    def batch_search_recipes(self, question: str, products: List[Dict], top_k: int = 10) -> Dict[str, List[Dict]]:
        """
        Simple, compatible version that works with any Qdrant client version.
        Major performance improvement with maximum compatibility.
        """
        if not products:
            return {}

        try:
            keywords = []
            for product in products:
                name = product.get("translated_name") or product.get("name", "")
                keywords.append(name)


            # Remove duplicates while preserving order
            keywords = list(dict.fromkeys(filter(None, keywords)))
            if not keywords:
                return {}

            # Create single comprehensive query
            base_query = self.generate_search_query(question)
            combined_query = f"{base_query} {', '.join(keywords)}"

            # Single embedding call
            embedding = self.embedding_model.embed_query(combined_query)

            # Calculate search limit
            search_limit = min(top_k * len(keywords) * 2, 150)

            hits = self.qdrant_client.search(
                collection_name="recipes",
                query_vector=embedding,
                limit=search_limit
            )

            # Initialize results
            results_by_keyword = {kw: [] for kw in keywords}
            seen_ids = set()
            keyword_counts = {kw: 0 for kw in keywords}

            # Process and distribute results
            for hit in hits:
                # Handle different payload access methods
                payload = getattr(hit, 'payload', None) or {}
                recipe_id = payload.get("id")

                if recipe_id in seen_ids:
                    continue

                ingredients = payload.get("ingredients", [])
                title = payload.get("title", "Unknown")

                # Find matching keywords
                matching_keywords = []
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    if (any(keyword_lower in str(ing).lower() for ing in ingredients) or
                        keyword_lower in title.lower()):
                        matching_keywords.append(keyword)

                # Fallback assignment if no matches
                if not matching_keywords:
                    # Assign to keyword with fewest results
                    matching_keywords = [min(keyword_counts.items(), key=lambda x: x[1])[0]]

                # Assign to first available keyword
                for keyword in matching_keywords:
                    if keyword_counts[keyword] < top_k:
                        # Handle different score access methods
                        score = getattr(hit, 'score', 0.0)

                        results_by_keyword[keyword].append({
                            "title": title,
                            "similarity": score,
                            "ingredients": ingredients,
                            "instructions": payload.get("instructions", ""),
                            "image_name": payload.get("image_name", ""),
                            "recipe_idx": recipe_id
                        })

                        seen_ids.add(recipe_id)
                        keyword_counts[keyword] += 1

                        self.logger.info(f"✔️ Retrieved for '{keyword}': {title} | score: {score:.3f}")
                        break

                # Early exit if all keywords satisfied
                if all(count >= top_k for count in keyword_counts.values()):
                    break

            # Log results
            total_results = sum(len(recipes) for recipes in results_by_keyword.values())
            self.logger.info(f"Search completed: {total_results} results across {len(keywords)} keywords")

            return results_by_keyword

        except Exception as e:
            self.logger.error(f"Vector search failed: {e}")
            return {kw: [] for kw in keywords}

    def generate_meal_plan_from_products(self, selected_products: List[Dict], question: str,
                                        days: int = 3, people: int = 2, dietary_restrictions: list = [],
                                        meal_types: list = [], excluded_ingredients: str = "") -> Optional[Dict]:
        """Generate meal plan from specific product list with batched recipe search"""
        if meal_types is []:
            meal_types = ["śniadanie", "obiad", "kolacja"]

        self.logger.info(f"Generating {days}-day plan for {people} people...")
        self.logger.info(f"Using {len(selected_products)} promotional products")
        self.logger.info(f"Dietary restrictions: {dietary_restrictions}")
        self.logger.info(f"Meal types: {meal_types}")
        self.logger.info(f"Excluded ingredients: {excluded_ingredients}")

        # Step 1: Build keyword-to-product map
        keyword_to_product = {}
        for product in selected_products:
            keyword = product.get("translated_name") or product.get("name", "")
            if keyword:
                keyword_to_product[keyword] = product

        # Step 2: Perform batched recipe search
        recipe_lookup = self.batch_search_recipes(question, selected_products, top_k=1)

        # Step 3: Prepare context for LLM
        products = ""
        recipies = ""

        for keyword, product in keyword_to_product.items():
            products += f"- {product['name']}: {product['price']} PLN ({product.get('discount_info', 'no discount')})\n"

            best_recipe = None
            if keyword in recipe_lookup and recipe_lookup[keyword]:
                best_recipe = recipe_lookup[keyword][0]

            if best_recipe:
                recipies += f"Suggested recipe for '{keyword}': {best_recipe['title']}\n"
                recipies += f"Image name: {best_recipe['image_name']}\n"
                recipies += f"Ingredients: {best_recipe['ingredients'][:1000]}...\n"
                recipies += f"Full recipe: {best_recipe['instructions'][:1000]}...\n\n"

        try:
            parsed_plan = self.chat_chain.invoke({
                "products": products,
                "recipies": recipies,
                "days": days,
                "people": people,
                "question": question,
                "dietary_restrictions": dietary_restrictions,
                "meal_types": meal_types,
                "excluded_ingredients": excluded_ingredients
            })

            parsed_plan = recalculate_prices_manual(parsed_plan)

            return parsed_plan

        except Exception as e:
            self.logger.error(f"Meal plan generation error: {e}")
            return None

    def get_all_products(self) -> List[str]:
        """Get all product names"""
        return [product['name'] for product in self.products]

    def quick_meal_plan(self, product_names: List[str], question, days: int = 2, people: int = 2, dietary_restrictions: list = [], meal_types: list = [], excluded_ingredients: str = "") -> Optional[Dict]:
        """Quick meal plan creation from selected products (by names)"""

        if meal_types is []:
            meal_types = ["śniadanie", "obiad", "kolacja"]

        selected_products = []

        for name in product_names:
            product = next((p for p in self.products if name.lower() in p['name'].lower()), None)
            if product:
                selected_products.append(product)
                self.logger.info(f"✅ Added: {product['name']}")
            else:
                self.logger.info(f"❌ Not found: {name}")

        if not selected_products:
            self.logger.info("❌ No products selected!")
            return {"status": "error", "message": "No products selected"}

        plan = self.generate_meal_plan_from_products(selected_products, question, days, people, dietary_restrictions, meal_types, excluded_ingredients)

        if plan:
            self.logger.info(f"\n✅ GENERATED MEAL PLAN:")
            self.logger.info(json.dumps(plan, ensure_ascii=False, indent=2))

            # Add status for API compatibility
            plan["status"] = "success"

            return plan
        else:
            return {"status": "error", "message": "Failed to generate plan"}

    def generate_plan_from_all_products(self, question, days: int = 1, people: int = 1, dietary_restrictions: list = [], meal_types: list = [], excluded_ingredients: str = "") -> Optional[Dict]:
        """Generate meal plan using all available products"""

        if meal_types is []:
            meal_types = ["śniadanie", "obiad", "kolacja"]

        all_product_names = self.get_all_products()

        print(f"\n📦 Available products ({len(all_product_names)}):")
        for i, name in enumerate(all_product_names, 1):
            print(f"{i:2d}. {name}")

        return self.quick_meal_plan(all_product_names, question, days, people, dietary_restrictions, meal_types, excluded_ingredients)

    def ask_rag(self, question: str, days: int = 1, people: int = 1, dietary_restrictions: list = [], meal_types: list = [], excluded_ingredients: str = "") -> Dict:
        """
        Main API function for frontend
        Returns the new clean format directly
        """
        try:
            if meal_types is []:
                meal_types = ["śniadanie", "obiad", "kolacja"]

            # translate to english for better accuracy
            translated_query = self.translate_to_english(question)

            # Generate a plan from all products
            plan = self.generate_plan_from_all_products(translated_query, days, people, dietary_restrictions, meal_types, excluded_ingredients)

            if plan and plan.get("status") == "success":
                return plan
            else:
                return {"status": "error", "message": "Could not generate meal plan"}

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}


# Initialize the API
meal_planner = MealPlannerAPI()

# Main function for frontend compatibility
def ask_rag(question: str, days: int = 1, people: int = 1, dietary_restrictions: list = [], meal_types: list = [], excluded_ingredients: str = "") -> dict:
    """
    Main API function that can be called from frontend
    Returns the new clean format
    """
    return meal_planner.ask_rag(question, days, people, dietary_restrictions, meal_types, excluded_ingredients)

# Additional utility functions
def quick_meal_plan(product_names: List[str], days: int = 2, people: int = 2, dietary_restrictions: list = [], meal_types: list = [], excluded_ingredients: str = ""):
    """Direct access to quick meal plan function"""
    return meal_planner.quick_meal_plan(product_names, "", days, people, dietary_restrictions, meal_types, excluded_ingredients)

def generate_plan_from_all_products(days: int = 1, people: int = 1, dietary_restrictions: list = [], meal_types: list = [], excluded_ingredients: str = ""):
    """Generate plan from all available products"""
    return meal_planner.generate_plan_from_all_products("", days, people, dietary_restrictions, meal_types, excluded_ingredients)
