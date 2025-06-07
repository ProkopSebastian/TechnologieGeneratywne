import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import openai
import pickle
from typing import List, Dict, Any, Optional
import os
from logger import get_logger
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient
from langchain.embeddings import OpenAIEmbeddings
import pandas as pd
from uuid import uuid4
from qdrant_client.models import VectorParams, Distance, PointStruct
from qdrant_client.http.models import SearchRequest
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
import openai
from prompts import search_query_prompt

class MealPlannerAPI:
    def __init__(self):
        self.API_KEY = os.getenv('OPENAI_API_KEY')
        self.RECIPE_DATA_PATH = "shared_data/recipe_embeddings.pkl"
        self.PRODUCTS_FILE = "shared_data/biedronka_offers_enhanced.json"
        
        self.client = openai.OpenAI(api_key=self.API_KEY)
        self.logger = get_logger("app-MealPlanner")

        self.qdrant_client = QdrantClient(host="qdrant", port=6333)
        self.embedding_model = OpenAIEmbeddings(openai_api_key=self.API_KEY)

        self.vectorstore = Qdrant(
            client=self.qdrant_client,
            collection_name="recipes",
            embeddings=self.embedding_model,
            content_payload_key="page_content",  # This tells LangChain to use 'page_content' as the main doc body
            metadata_payload_key=None            # This tells LangChain to treat everything else as metadata
        )

        self.llm_quick = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0,
            max_tokens=20
        )
        self.search_query_chain = LLMChain(llm=self.llm_quick, prompt=search_query_prompt)
        self.qdrant = QdrantClient(host="qdrant", port=6333)
        
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

                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Translate the following grocery product name from Polish to English. Only respond with a direct, short translation."},
                        {"role": "user", "content": original_name}
                    ],
                    temperature=0,
                    max_tokens=20
                )

                translated = response.choices[0].message.content.strip()
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
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Translate the user's message to English."},
                    {"role": "user", "content": text}
                ],
                temperature=0,
                max_tokens=60
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            return text  # fallback to original if translation fails

    def generate_search_query(self, user_query: str) -> str:
        """
        Convert user query into a concise recipe search query using LangChain.
        """
        try:
            result = self.search_query_chain.run(user_request=user_query)
            rewritten = result.strip()
            self.logger.info(f"Rewritten query: {rewritten}")
            return rewritten
        except Exception as e:
            self.logger.error(f"LangChain search query generation failed: {e}")
            return user_query


    def batch_search_recipes(self, question: str, products: List[Dict], top_k: int = 10) -> Dict[str, List[Dict]]:
        """
        Optimized batch search of recipes using Qdrant + text-embedding-3-small.
        Ensures each recipe (based on its 'id') is only returned once across all keywords.
        Returns: keyword -> list of top_k unique recipes
        """
        # Extract unique keywords from products
        # keywords = sorted({kw for product in products for kw in product.get("english_keywords", [])})

        # use english name for better accuracy
        keywords = sorted({
            self.translate_to_english(product.get("translated_name", product.get("name", "")))
            for product in products
        })
        if not keywords:
            return {}

        try:
            # Generate prompt base
            base_query = self.generate_search_query(question)
            queries = [
                f"{base_query}. Focus on recipes using: {kw}. Prioritize the user’s intent."
                for kw in keywords
            ]

            # Batch embed all queries
            embeddings = self.embedding_model.embed_documents(queries)

            # Prepare search requests
            search_requests = [
                SearchRequest(
                    vector=embedding,
                    limit=top_k,
                    with_payload=True,
                    with_vector=False
                )
                for embedding in embeddings
            ]

            # Perform batch search
            results = self.qdrant_client.search_batch(
                collection_name="recipes",
                requests=search_requests
            )

            # Initialize result containers
            seen_ids = set()
            results_by_keyword = {}

            for keyword, hits in zip(keywords, results):
                recipes = []
                for hit in hits:
                    payload = hit.payload or {}
                    recipe_id = payload.get("id")

                    # Skip duplicates globally
                    if recipe_id in seen_ids:
                        continue
                    seen_ids.add(recipe_id)

                    title = payload.get("title", "Unknown")
                    self.logger.info(f"✔️ Retrieved: {title} | image: {payload.get('image_name', '')}")
                    
                    recipes.append({
                        "title": title,
                        "similarity": hit.score,
                        "ingredients": payload.get("ingredients", []),
                        "instructions": payload.get("instructions", ""),
                        "image_name": payload.get("image_name", ""),
                        "recipe_idx": recipe_id
                    })

                results_by_keyword[keyword] = recipes

            return results_by_keyword

        except Exception as e:
            self.logger.error(f"Batch vector search failed: {e}")
            return {kw: [] for kw in keywords}

    def search_recipes_by_keywords(self, question: str, keywords: List[str], top_k: int = 5) -> List[Dict]:
        """Search recipes using LangChain + Qdrant vector DB"""
        if not keywords:
            return []

        try:
            query = f"{question} " + " ".join(keywords)

            #results = self.vectorstore.similarity_search_with_score(query, k=top_k)
            self.retriever.search_kwargs["k"] = top_k
            results = self.retriever.invoke(query)

            out = []
            for doc in results:
                meta = doc.metadata or {}
                out.append({
                    "title": doc.page_content[:100].split(".")[0],  # crude title fallback
                    "similarity": "N/A",
                    "ingredients": meta.get("ingredients", ""),
                    "instructions": meta.get("instructions", ""),
                    "image_name": meta.get("image_name", ""),
                    "recipe_idx": meta.get("id", -1)
                })

            return out

        except Exception as e:
            self.logger.error(f"Vector search error: {e}")
            return []


    def generate_meal_plan_from_products(self, selected_products: List[Dict], question: str,
                                     days: int = 3, people: int = 2) -> Optional[Dict]:
        """Generate meal plan from specific product list with batched recipe search"""
        self.logger.info(f"Generating {days}-day plan for {people} people...")
        self.logger.info(f"Using {len(selected_products)} promotional products")

        # Batch recipe search (1 per unique keyword)
        recipe_lookup = self.batch_search_recipes(question, selected_products, top_k=1)

        # Prepare context for LLM
        context = f"AVAILABLE PROMOTIONAL PRODUCTS:\n"

        for product in selected_products:
            context += f"- {product['name']}: {product['price']} PLN ({product.get('discount_info', 'no discount')})\n"

            keywords = product.get('english_keywords', [])
            best_recipe = None

            # Pick first available recipe from matching keywords
            for keyword in keywords:
                if keyword in recipe_lookup and recipe_lookup[keyword]:
                    best_recipe = recipe_lookup[keyword][0]
                    break

            if best_recipe:
                context += f"  Suggested recipe: {best_recipe['title']}\n"
                context += f"  Image name: {best_recipe['image_name']}\n"
                context += f"  Ingredients: {best_recipe['ingredients'][:1000]}...\n"
                context += f"  Full recipe: {best_recipe['instructions'][:1000]}...\n"

        # LLM prompt
        prompt = f"""Create a detailed meal plan for {days} days for {people} people using promotional products from Biedronka.

    {context}

    ADDITIONAL INSTRUCTIONS:
    You are preparing a diet for person that wants the following: "{question}"

    RULES:
    - Use as many promotional products as possible
    - One meal can include multiple promotional products
    - Create varied, healthy meals (breakfast, lunch, dinner)
    - STRICT DIETARY RULE: If the question requests a vegetarian diet, DO NOT use meat, poultry, or fish in any meal. You can use plant-based alternatives like tofu, lentils, eggs, or dairy.
    - Use suggested recipes as inspiration - you can copy their instructions directly
    - Include precise quantities for all ingredients (e.g., "200g tofu")
    - Provide detailed step-by-step cooking instructions - if using a suggested recipe, copy its instructions directly
    - Calculate estimated total cost
    - You can add basic ingredients (bread, eggs, milk, etc.)


    Return the response in JSON format with Polish text:
    {{
    "plan_info": {{
        "days": {days},
        "people": {people},
        "estimated_total_cost": "XX.XX PLN"
    }},
    "meals": [
        {{
        "day": 1,
        "type": "breakfast",
        "name": "Meal name in Polish",
        "image_name": "copy image name from suggested recipe only if you used it, otherwise leave empty",
        "main_products": [
            {{
            "name": "Product name",
            "quantity": "200g",
            "price": "X.XX PLN"
            }}
        ],
        "additional_ingredients": [
            {{
            "name": "Basic ingredient",
            "quantity": "100ml",
            "estimated_price": "X.XX PLN"
            }}
        ],
        "instructions": "Detailed step-by-step preparation instructions in Polish. Should be very specific with cooking times, temperatures, and techniques. If using a suggested recipe, you can copy its instructions directly.",
        "prep_time": "XX min",
        "cooking_time": "XX min"
        }}
    ],
    "shopping_summary": {{
        "promotional_products_cost": "XX.XX PLN",
        "additional_ingredients_cost": "XX.XX PLN",
        "total_savings": "Calculate savings from promotions in PLN"
    }}
    }}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  #gpt-4o or gpt-3.5-turbo-1106 for faster results
                messages=[
                    {"role": "system", "content": "You are an expert meal planner. Respond ONLY in the specified JSON format with Polish text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=6000
            )

            result = response.choices[0].message.content.strip()

            # Save debug info
            with open("shared_data/debug_meal_plan_request.txt", "w", encoding='utf-8') as f:
                f.write(f"Prompt:\n{prompt}\n\nResponse:\n{result}\n")

            # Clean JSON response
            if result.startswith('```json'):
                result = result.replace('```json', '').replace('```', '').strip()

            parsed_plan = json.loads(result)
            return parsed_plan

        except Exception as e:
            self.logger.error(f"Meal plan generation error: {e}")
            return None


    def get_all_products(self) -> List[str]:
        """Get all product names"""
        return [product['name'] for product in self.products]

    def quick_meal_plan(self, product_names: List[str], question, days: int = 2, people: int = 2) -> Optional[Dict]:
        """Quick meal plan creation from selected products (by names)"""
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
        
        plan = self.generate_meal_plan_from_products(selected_products, question, days, people)
        
        if plan:
            self.logger.info(f"\n✅ GENERATED MEAL PLAN:")
            self.logger.info(json.dumps(plan, ensure_ascii=False, indent=2))
            
            # Add status for API compatibility
            plan["status"] = "success"
            
            return plan
        else:
            return {"status": "error", "message": "Failed to generate plan"}

    def generate_plan_from_all_products(self, question, days: int = 1, people: int = 1) -> Optional[Dict]:
        """Generate meal plan using all available products"""
        all_product_names = self.get_all_products()
        
        print(f"\n📦 Available products ({len(all_product_names)}):")
        for i, name in enumerate(all_product_names, 1):
            print(f"{i:2d}. {name}")
        
        return self.quick_meal_plan(all_product_names, question, days, people)

    def ask_rag(self, question: str, days: int = 1, people: int = 1) -> Dict:
        """
        Main API function for frontend
        Returns the new clean format directly
        """
        try:
            # translate to english for better accuracy
            translated_query = self.translate_to_english(question)

            # Generate a plan from all products
            plan = self.generate_plan_from_all_products(translated_query, days, people)
            
            if plan and plan.get("status") == "success":
                return plan
            else:
                return {"status": "error", "message": "Could not generate meal plan"}
                
        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}


# Initialize the API
meal_planner = MealPlannerAPI()
#meal_planner.embed_and_push_test_json()

# Main function for frontend compatibility
def ask_rag(question: str, days: int = 1, people: int = 1) -> dict:
    """
    Main API function that can be called from frontend
    Returns the new clean format
    """
    return meal_planner.ask_rag(question, days, people)

# Additional utility functions
def quick_meal_plan(product_names: List[str], days: int = 2, people: int = 2):
    """Direct access to quick meal plan function"""
    return meal_planner.quick_meal_plan(product_names, days, people)

def generate_plan_from_all_products(days: int = 1, people: int = 1):
    """Generate plan from all available products"""
    return meal_planner.generate_plan_from_all_products(days, people)