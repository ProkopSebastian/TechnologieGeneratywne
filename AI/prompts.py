from langchain.prompts import PromptTemplate, ChatPromptTemplate

search_query_prompt = PromptTemplate(
    input_variables=["user_request"],
    template=(
        "Rewrite the following user request as a short, effective recipe search query (3–6 words):\n"
        "User request: {user_request}\n"
        "Search query:"
    )
)


translation_prompt = ChatPromptTemplate.from_messages([
    ("system", "Translate the following grocery product name from Polish to English. Only respond with a direct, short translation."),
    ("user", "{product_name}")
])

generic_translation_prompt = ChatPromptTemplate.from_messages([
    ("system", "Translate the user's message to English."),
    ("user", "{input_text}")
])

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert meal planner. Respond ONLY in the specified JSON format with Polish text."),
    ("user", """Create a detailed meal plan for {days} days for {people} people using promotional products from Biedronka.

AVAIABLE PRODUCTS
{products}
SUGGESTED RECIPIES
{recipies}

ADDITIONAL INSTRUCTIONS:
You are preparing a diet for person that wants the following: "{question}"

DIETARY RESTRICTIONS: {dietary_restrictions}
MEAL TYPES TO INCLUDE: {meal_types}
EXCLUDED INGREDIENTS: {excluded_ingredients}

RULES:
- Use as many promotional products as possible
- One meal can include multiple promotional products
- Create varied, healthy meals matching the requested meal types
- STRICT DIETARY RESTRICTIONS: Follow all dietary restrictions exactly:
  * If "Wegetariańskie" is in restrictions, DO NOT use meat, poultry, or fish in any meal
  * If "Bezglutenowe" is in restrictions, avoid wheat, gluten-containing grains and products
  * If "Bez laktozy" is in restrictions, avoid dairy products or use lactose-free alternatives
  * If "Keto" is in restrictions, focus on high-fat, low-carb ingredients
- EXCLUDED INGREDIENTS: Do NOT use any ingredients mentioned in excluded ingredients list
- MEAL TYPES: Only create meals of the types specified in meal_types list
- Use suggested recipes as inspiration - you can copy their instructions directly
- Include precise quantities for all ingredients (e.g., "200g tofu")
- Provide detailed step-by-step cooking instructions - if using a suggested recipe, copy its instructions directly
- Calculate estimated total cost
- You can add basic ingredients (bread, eggs, milk, etc.) as long as they don't violate restrictions

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
}}""")
])

recalculate_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a strict cost calculator. Do not correct price in products. Only correct numeric values (promotional_products_cost, additional_ingredients_cost, total_savings, estimated_total_cost) in this JSON, return a valid JSON with exactly the same structure (You only change numeric values)."),
    ("user", "{raw_json}")
])
