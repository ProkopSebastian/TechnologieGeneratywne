import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import openai
import pickle
from typing import List, Dict, Any, Optional
import os

class MealPlannerAPI:
    def __init__(self):
        self.API_KEY = os.getenv('OPENAI_API_KEY')
        self.RECIPE_DATA_PATH = "shared_data/recipe_embeddings.pkl"
        self.PRODUCTS_FILE = "shared_data/biedronka_offers_enhanced.json"
        
        self.client = openai.OpenAI(api_key=self.API_KEY)
        
        # Load data
        self._load_data()
    
    def _load_data(self):
        """Load recipe embeddings and product data"""
        try:
            # Load recipe embeddings
            with open(self.RECIPE_DATA_PATH, 'rb') as f:
                self.recipe_data = pickle.load(f)
            
            # Load products
            with open(self.PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                products_data = json.load(f)
            
            self.products = products_data['products']
            
            print(f"Załadowano {len(self.recipe_data['recipes_df'])} przepisów")
            print(f"Załadowano {len(self.products)} produktów z Biedronki")
            
        except Exception as e:
            print(f"Błąd ładowania danych: {e}")
            raise

    def search_recipes_by_keywords(self, keywords: List[str], top_k: int = 5) -> List[Dict]:
        """Search recipes using English keywords"""
        if not keywords:
            return []
        
        try:
            # Create query from keywords
            query = " ".join(keywords) + " recipes"
            
            # Get query embedding
            query_response = self.client.embeddings.create(
                input=[query],
                model='text-embedding-3-small'
            )
            query_embedding = query_response.data[0].embedding
            
            # Calculate similarities
            recipe_embeddings = np.array(self.recipe_data['embeddings'])
            similarities = cosine_similarity([query_embedding], recipe_embeddings)[0]
            
            # Get top results
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                recipe = self.recipe_data['recipes_df'][idx]
                results.append({
                    'title': recipe['Title'],
                    'similarity': similarities[idx],
                    'ingredients': str(recipe['Cleaned_Ingredients']),
                    'instructions': recipe['Instructions'],
                    'recipe_idx': idx
                })
            
            return results
            
        except Exception as e:
            print(f"Błąd wyszukiwania przepisów: {e}")
            return []

    def generate_meal_plan_from_products(self, selected_products: List[Dict], 
                                       days: int = 3, people: int = 2) -> Optional[Dict]:
        """Generate meal plan from specific product list"""
        print(f"Generowanie planu na {days} dni dla {people} osób...")
        print(f"Używane produkty: {len(selected_products)}")
        
        # Prepare context for LLM
        context = f"DOSTĘPNE PRODUKTY PROMOCYJNE:\n"
        
        for product in selected_products:
            context += f"- {product['name']}: {product['price']} PLN ({product.get('discount_info', 'brak zniżki')})\n"
            
            # Add best recipe as inspiration
            keywords = product.get('english_keywords', [])
            if keywords:
                recipes = self.search_recipes_by_keywords(keywords, top_k=1)
                if recipes:
                    best_recipe = recipes[0]
                    context += f"  Sugerowany przepis: {best_recipe['title']}\n"
                    context += f"  Składniki: {best_recipe['ingredients'][:1000]}...\n" # Limit to 220 characters
                    context += f"  Cały przepis: {best_recipe['instructions'][:1000]}...\n" # Limit to 220 characters
        
        # LLM prompt
        prompt = f"""Stwórz plan posiłków na {days} dni dla {people} osób, wykorzystując produkty promocyjne z Biedronki.

{context}

ZASADY:
- Użyj jak najwięcej produktów promocyjnych z listy
- Stwórz różnorodne, zdrowe posiłki (śniadanie, lunch, kolacja)
- Wykorzystaj sugerowane przepisy jako inspirację
- Podaj oszacowany całkowity koszt
- Możesz dodać podstawowe składniki (chleb, jajka, mleko, etc.)

Zwróć odpowiedź w formacie JSON:
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
      "name": "Nazwa posiłku",
      "main_products": ["Produkty z listy promocyjnej"],
      "additional_ingredients": ["Podstawowe składniki jeśli potrzeba"],
      "instructions": "Kroki przygotowania posiłku",
      "prep_time": "XX min"
    }}
  ],
  "shopping_summary": {{
    "promotional_products_cost": "XX.XX PLN",
    "additional_ingredients_cost": "XX.XX PLN",
    "total_savings": "Ile zaoszczędzono dzięki promocjom"
  }}
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Jesteś ekspertem od planowania posiłków. Odpowiadasz TYLKO w formacie JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=8000
            )
            
            result = response.choices[0].message.content.strip()
            
            # Zapisz całe zapytanie i odpowiedź do pliku debugowania
            with open("shared_data/debug_meal_plan_request.txt", "w", encoding='utf-8') as f:
                f.write(f"Prompt:\n{prompt}\n\nResponse:\n{result}\n")


            # Clean JSON response
            if result.startswith('```json'):
                result = result.replace('```json', '').replace('```', '').strip()
            
            parsed_plan = json.loads(result)
            return parsed_plan
            
        except Exception as e:
            print(f"Błąd generowania planu: {e}")
            return None

    def get_all_products(self) -> List[str]:
        """Get all product names"""
        return [product['name'] for product in self.products]

    def quick_meal_plan(self, product_names: List[str], days: int = 2, people: int = 2) -> Optional[Dict]:
        """Quick meal plan creation from selected products (by names)"""
        selected_products = []
        
        for name in product_names:
            product = next((p for p in self.products if name.lower() in p['name'].lower()), None)
            if product:
                selected_products.append(product)
                print(f"✅ Dodano: {product['name']}")
            else:
                print(f"❌ Nie znaleziono: {name}")
        
        if not selected_products:
            print("❌ Nie wybrano żadnych produktów!")
            return {"status": "error", "message": "Nie wybrano żadnych produktów"}
        
        plan = self.generate_meal_plan_from_products(selected_products, days, people)
        
        if plan:
            print(f"\n✅ WYGENEROWANY PLAN:")
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            
            # Add status for API compatibility
            plan["status"] = "success"
            
            return plan
        else:
            return {"status": "error", "message": "Nie udało się wygenerować planu"}

    def generate_plan_from_all_products(self, days: int = 1, people: int = 1) -> Optional[Dict]:
        """Generate meal plan using all available products"""
        all_product_names = self.get_all_products()
        
        print(f"\n📦 Produkty do wykorzystania ({len(all_product_names)}):")
        for i, name in enumerate(all_product_names, 1):
            print(f"{i:2d}. {name}")
        
        return self.quick_meal_plan(all_product_names, days, people)

    def ask_rag(self, question: str, days: int = 1, people: int = 1) -> Dict:
        """
        Main API function for frontend
        Returns the new clean format directly
        """
        try:
            # Generate a plan from all products
            # In the future, you can extend this to parse the question for specific requirements
            plan = self.generate_plan_from_all_products(days, people)
            
            if plan and plan.get("status") == "success":
                return plan
            else:
                return {"status": "error", "message": "Could not generate meal plan"}
                
        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}


# Initialize the API
meal_planner = MealPlannerAPI()

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