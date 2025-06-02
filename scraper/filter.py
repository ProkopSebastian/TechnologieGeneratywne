import json
import openai
from typing import List, Dict, Any, Set
import time
from pathlib import Path
import os
import sys

class ProductFilter:
    def __init__(self, api_key: str):
        """
        Agent LLM do filtrowania produktów dla meal plannera
        """
        self.client = openai.OpenAI(api_key=api_key)
        
    def create_filter_prompt(self, product_details_batch: List[Dict[str, Any]]) -> str:
        """
        Tworzy prompt w języku angielskim do analizy i filtrowania produktów,
        uwzględniając nazwy i angielskie słowa kluczowe.
        """
        products_list_str = ""
        for i, details in enumerate(product_details_batch):
            name = details['name']
            keywords = details.get('keywords', [])
            keyword_str = ', '.join(keywords) if keywords else 'N/A'
            products_list_str += f"{i+1}. Name: {name} (Keywords: {keyword_str})\n"
        
        prompt = f"""You are an expert at analyzing supermarket product lists for a meal planning application. Your task is to identify products that should be REMOVED because they are not typical food ingredients for cooking meals.

PRODUCT LIST:
{products_list_str}

TASK: Identify the 1-based numbers of the products to REMOVE from the list based on the following criteria.

Beware that product names are givem in Polish, translate the, for yourself to English if needed, using the keywords provided in English.

REMOVE IF THE PRODUCT IS:
- A beverage (e.g., tea, coffee, juice, water, alcohol, soda, plant-based milk like almond/soy/oat milk when listed as a standalone drink rather than a cooking ingredient).
- Cosmetics, personal hygiene items, cleaning supplies (e.g., shampoo, soap, deodorant, detergent, fabric softener, toilet paper).
- Household items not for cooking (e.g., batteries, light bulbs, kitchen utensils like storage containers, cutlery unless specified as disposable for events).
- Supplements, medicines, vitamins.
- Sweets and snacks not typically used as an ingredient in meal preparation (e.g., candy bars, chips, lollipops, chewing gum, ice cream cones). However, keep items like baking chocolate, sugar, flour, cocoa powder, honey.
- Technical products, electronics.
- Pet food or pet supplies.
- Coffee capsules or pods
- Baby diapers, baby wipes, or baby formula (unless it's a food item that adults might also use in cooking, e.g., some fruit purees).
- Oils and fats
- Milk (dairy and plant-based alternatives like almond, soy, oat milk) IF it's primarily a drinking product (e.g., "Almond Milk Drink 1L", "Chocolate Milk"). However, if it's an ingredient like "Coconut Milk for Cooking," "Condensed Milk," "Cooking Cream," or plain milk that can be used for cooking, it SHOULD BE KEPT. Be very discerning with milk and oils.
- Pre-made sauces or condiments that are typically accompaniments rather than core ingredients for a meal might be considered for removal if the list needs significant trimming, but prioritize removing non-food items first.

PRIORITIZE KEEPING INGREDIENTS FOR MEALS. If a product is ambiguous but could be used in cooking (e.g., plain yogurt, cheese, bread, canned vegetables, fruits), lean towards KEEPING it. The goal is to curate a list of items for grocery shopping to cook meals.

OUTPUT FORMAT (JSON ONLY):
{{
  "to_remove": [1, 5, 12, 23] // List of 1-based indices from the provided list
}}

Respond ONLY with JSON, without any additional comments or explanations. Ensure the JSON is valid.
"""
        return prompt
    
    def get_products_to_remove(self, product_details_batch: List[Dict[str, Any]]) -> Set[int]:
        """
        Pobiera listę 1-based indeksów produktów do usunięcia dla danego batcha.
        Zwraca set indeksów.
        """
        if not product_details_batch:
            return set()
            
        prompt = self.create_filter_prompt(product_details_batch)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert shopping list reviewer. Your task is to reduce the shopping list by removing items not used for cooking meals. You ONLY respond in JSON format. Ensure the output is a valid JSON object with the key 'to_remove' containing a list of numbers."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.05,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            result_content = response.choices[0].message.content
            # Czasem LLM może zwrócić JSON w bloku markdown, usuwamy go
            if result_content.startswith("```json"):
                result_content = result_content.strip("```json").strip("```").strip()

            result = json.loads(result_content)
            indices_to_remove = set(result.get("to_remove", []))
            
            # Walidacja indeksów (czy są w zakresie batcha)
            valid_indices = set()
            max_index_in_batch = len(product_details_batch)
            for idx in indices_to_remove:
                if 1 <= idx <= max_index_in_batch:
                    valid_indices.add(idx)
                else:
                    print(f"⚠️ Ostrzeżenie: LLM zwrócił niepoprawny indeks {idx} dla batcha o rozmiarze {max_index_in_batch}. Indeks zignorowany.")
            return valid_indices
            
        except json.JSONDecodeError as e:
            print(f"❌ Błąd dekodowania JSON od API: {e}")
            print(f"   Otrzymana odpowiedź: {response.choices[0].message.content if response and response.choices else 'Brak odpowiedzi'}")
            return set()
        except Exception as e:
            print(f"❌ Błąd API OpenAI: {e}")
            return set()
    
    def filter_products_file(self, input_file: str, output_file: str = None, batch_size: int = 40):
        """
        Główna funkcja - wczytuje JSON, filtruje produkty, zapisuje
        """
        if not Path(input_file).exists():
            print(f"❌ Plik wejściowy nie istnieje: {input_file}")
            return None
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Błąd wczytywania pliku: {e}")
            return None
        
        if 'products' not in data or not isinstance(data['products'], list):
            print("❌ Brak klucza 'products' w danych lub nie jest listą.")
            return None
        
        all_products_original = data['products']
        total_products_original_count = len(all_products_original)
        
        if total_products_original_count == 0:
            print("⚠️ Brak produktów do przetworzenia.")
            # Zapisz plik z aktualizacją statystyk, nawet jeśli jest pusty
            data['total_products'] = 0
            if 'filter_info' not in data:
                data['filter_info'] = {}
            data['filter_info'].update({
                'filtered_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'original_count': 0,
                'filtered_count': 0,
                'removed_count': 0,
                'batch_size_used': batch_size
            })
            if output_file is None:
                output_file = input_file.replace('.json', '_filtered.json')
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"✅ Zapisano pusty plik wynikowy do: {output_file}")
            except Exception as e:
                print(f"❌ Błąd zapisu pustego pliku wynikowego: {e}")
            return output_file

        print(f"🔍 Analizowanie {total_products_original_count} produktów do filtrowania...")
        
        # Przygotuj listę szczegółów produktów (nazwa + słowa kluczowe)
        product_details_list = [
            {'name': p.get('name', 'Brak nazwy'), 'keywords': p.get('english_keywords', [])} 
            for p in all_products_original
        ]
        
        all_indices_to_remove_0_based = set()
        
        if total_products_original_count <= batch_size:
            print(f"📦 Przetwarzanie wszystkich {total_products_original_count} produktów naraz...")
            # LLM zwraca indeksy 1-based dla przekazanego batcha
            indices_1_based_from_llm = self.get_products_to_remove(product_details_list)
            # Konwersja na 0-based
            all_indices_to_remove_0_based = {idx - 1 for idx in indices_1_based_from_llm}
            print(f" 🗑️ Do usunięcia (z tego batcha): {len(all_indices_to_remove_0_based)} produktów")
        else:
            print(f"📦 Przetwarzanie w batchach po {batch_size} produktów...")
            for i in range(0, total_products_original_count, batch_size):
                batch_start_idx_0_based = i
                batch_end_idx_0_based = min(i + batch_size, total_products_original_count)
                
                current_batch_details = product_details_list[batch_start_idx_0_based:batch_end_idx_0_based]
                batch_num = batch_start_idx_0_based // batch_size + 1
                
                print(f"📦 Batch {batch_num}: produkty {batch_start_idx_0_based + 1}-{batch_end_idx_0_based}")
                
                # LLM zwraca indeksy 1-based dla bieżącego batcha
                batch_indices_1_based_from_llm = self.get_products_to_remove(current_batch_details)
                
                # Konwersja na globalne indeksy 0-based
                # idx_1_based_in_batch odnosi się do pozycji w `current_batch_details`
                # (idx_1_based_in_batch - 1) daje 0-based indeks w `current_batch_details`
                # dodanie `batch_start_idx_0_based` mapuje go na globalny 0-based indeks
                global_indices_for_this_batch_0_based = {
                    (idx_1_based_in_batch - 1) + batch_start_idx_0_based 
                    for idx_1_based_in_batch in batch_indices_1_based_from_llm
                }
                
                all_indices_to_remove_0_based.update(global_indices_for_this_batch_0_based)
                
                print(f"  🗑️ Do usunięcia (z tego batcha): {len(batch_indices_1_based_from_llm)} produktów")
                print(f"  🗑️ Sumarycznie do usunięcia: {len(all_indices_to_remove_0_based)} produktów")
                
                if batch_end_idx_0_based < total_products_original_count:
                    time.sleep(1) # Krótka pauza między batchami, aby nie przeciążać API
        
        # Pokaż produkty do usunięcia (na podstawie globalnych indeksów 0-based)
        products_marked_for_removal_names = []
        for idx_0_based in sorted(list(all_indices_to_remove_0_based)):
            if 0 <= idx_0_based < total_products_original_count:
                products_marked_for_removal_names.append(all_products_original[idx_0_based].get('name', 'Brak nazwy'))
        
        if products_marked_for_removal_names:
            print(f"\n🗑️ PRODUKTY DO USUNIĘCIA ({len(products_marked_for_removal_names)}):")
            for name in products_marked_for_removal_names[:15]: # Pokaż maksymalnie 15
                print(f"  • {name}")
            if len(products_marked_for_removal_names) > 15:
                print(f"  ... i {len(products_marked_for_removal_names) - 15} więcej.")
        else:
            print("\n👍 Żadne produkty nie zostały oznaczone do usunięcia przez LLM.")
            
        # Utwórz listę przefiltrowanych produktów
        filtered_products = [
            product for i, product in enumerate(all_products_original) 
            if i not in all_indices_to_remove_0_based
        ]
        
        data['products'] = filtered_products
        data['total_products'] = len(filtered_products)
        
        if 'filter_info' not in data:
            data['filter_info'] = {}
        
        data['filter_info'].update({
            'filtered_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'original_count': total_products_original_count,
            'filtered_count': len(filtered_products),
            'removed_count': len(all_indices_to_remove_0_based), # Używamy len zbioru indeksów
            'batch_size_used': batch_size
        })
        
        if output_file is None:
            input_path = Path(input_file)
            output_file = input_path.parent / f"{input_path.stem}_filtered{input_path.suffix}"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ Przefiltrowano produkty:")
            print(f"  📊 Oryginalnie: {total_products_original_count} produktów")
            print(f"  ✂️ Usunięto: {len(all_indices_to_remove_0_based)} produktów")
            print(f"  📝 Pozostało: {len(filtered_products)} produktów")
            print(f"  💾 Zapisano do: {output_file}")
            
            return str(output_file)
            
        except Exception as e:
            print(f"❌ Błąd zapisu pliku: {e}")
            return None

def main():
    print("🍳 Uruchamiam LLM Product Filter dla meal plannera...")
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Brak OPENAI_API_KEY w zmiennych środowiskowych. Ustaw ją i spróbuj ponownie.")
        sys.exit(1)
    
    base_path = Path(__file__).parent 
    input_file_path = os.getenv('FILTER_INPUT_FILE', "/shared/biedronka_offers_enhanced.json")
    output_file_path = os.getenv('FILTER_OUTPUT_FILE', "/shared/biedronka_offers_filtered.json")
    
    # Konfiguracja batch size
    try:
        batch_size = int(os.getenv('FILTER_BATCH_SIZE', 40))
    except ValueError:
        print("⚠️ Niepoprawna wartość dla FILTER_BATCH_SIZE. Używam domyślnej: 40.")
        batch_size = 40

    if not Path(input_file_path).exists():
        print(f"❌ Plik wejściowy nie istnieje: {input_file_path}")
        print("💡 Upewnij się, że plik 'biedronka_offers_enhanced.json' (lub inny podany) istnieje, np. po uruchomieniu skryptu 'enhancer.py'.")
        sys.exit(1)
    
    try:
        filter_agent = ProductFilter(api_key=api_key)
        result_file = filter_agent.filter_products_file(
            input_file=str(input_file_path),
            output_file=str(output_file_path),
            batch_size=batch_size
        )
        
        if result_file:
            print(f"\n🎉 Filtrowanie zakończone pomyślnie! Wynik w pliku: {result_file}")
        else:
            print("\n❌ Filtrowanie nie powiodło się.")
            sys.exit(1)
            
    except Exception as e:
        import traceback
        print(f"💥 Nieoczekiwany krytyczny błąd: {e}")
        print(traceback.format_exc()) # Dodatkowy traceback dla debugowania
        sys.exit(1)

if __name__ == "__main__":
    main()