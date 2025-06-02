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
            
            print(f"Loaded {len(self.recipe_data['recipes_df'])} recipes")
            print(f"Loaded {len(self.products)} products from Biedronka")
            
        except Exception as e:
            print(f"Error loading data: {e}")
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
            print(f"Recipe search error: {e}")
            return []

    def generate_meal_plan_from_products(self, selected_products: List[Dict], 
                                       days: int = 3, people: int = 2) -> Optional[Dict]:
        """Generate meal plan from specific product list"""
        print(f"Generating {days}-day plan for {people} people...")
        print(f"Using {len(selected_products)} promotional products")
        
        # Prepare context for LLM
        context = f"AVAILABLE PROMOTIONAL PRODUCTS:\n"
        
        for product in selected_products:
            context += f"- {product['name']}: {product['price']} PLN ({product.get('discount_info', 'no discount')})\n"
            
            # Add best recipe as inspiration
            keywords = product.get('english_keywords', [])
            if keywords:
                recipes = self.search_recipes_by_keywords(keywords, top_k=1)
                if recipes:
                    best_recipe = recipes[0]
                    context += f"  Suggested recipe: {best_recipe['title']}\n"
                    context += f"  Ingredients: {best_recipe['ingredients'][:1000]}...\n"
                    context += f"  Full recipe: {best_recipe['instructions'][:1000]}...\n"
        
        # LLM prompt in English with detailed instructions
        prompt = f"""Create a detailed meal plan for {days} days for {people} people using promotional products from Biedronka.

{context}

RULES:
- Use as many promotional products as possible
- Create varied, healthy meals (breakfast, lunch, dinner)
- Use suggested recipes as inspiration - you can copy their instructions directly
- Include precise quantities for all ingredients (e.g., "200g chicken breast")
- Provide detailed step-by-step cooking instructions
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
    "total_savings": "Savings from promotions in PLN"
  }}
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert meal planner. Respond ONLY in the specified JSON format with Polish text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=8000
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
            print(f"Meal plan generation error: {e}")
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
                print(f"✅ Added: {product['name']}")
            else:
                print(f"❌ Not found: {name}")
        
        if not selected_products:
            print("❌ No products selected!")
            return {"status": "error", "message": "No products selected"}
        
        plan = self.generate_meal_plan_from_products(selected_products, days, people)
        
        if plan:
            print(f"\n✅ GENERATED MEAL PLAN:")
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            
            # Add status for API compatibility
            plan["status"] = "success"
            
            return plan
        else:
            return {"status": "error", "message": "Failed to generate plan"}

    def generate_plan_from_all_products(self, days: int = 1, people: int = 1) -> Optional[Dict]:
        """Generate meal plan using all available products"""
        all_product_names = self.get_all_products()
        
        print(f"\n📦 Available products ({len(all_product_names)}):")
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