import json
import openai
from typing import List, Dict, Any
import time
from pathlib import Path
import os
import sys

class ProductKeywordsEnhancer:
    def __init__(self, api_key: str):
        """
        Agent LLM do dodawania angielskich słów kluczowych do produktów Biedronki
        """
        self.client = openai.OpenAI(api_key=api_key)
        
    def create_batch_prompt(self, products: List[Dict]) -> str:
        """
        Tworzy sprytny prompt dla wielu produktów naraz - oszczędność tokenów
        """
        # Wyciągamy tylko nazwy produktów
        product_names = [p['name'] for p in products]
        
        prompt = f"""Dodaj angielskie słowa kluczowe dla produktów spożywczych z polskiej sieci Biedronka.

PRODUKTY:
{chr(10).join([f"{i+1}. {name}" for i, name in enumerate(product_names)])}

ZADANIE: Dla każdego produktu podaj 3-5 angielskich słów kluczowych które pomogą w wyszukiwaniu przepisów.

FORMAT ODPOWIEDZI (JSON):
{{
  "keywords": [
    ["sausage", "meat", "pork", "deli"],
    ["bread", "bakery", "wheat", "loaf"],
    ...
  ]
}}

ZASADY:
- Używaj podstawowych angielskich nazw składników
- Skupiaj się na kategoriach jedzenia (meat, dairy, vegetables, etc.)
- Unikaj marek i szczegółów - tylko typy jedzenia
- Odpowiedz TYLKO JSON, bez dodatkowych komentarzy"""
        
        return prompt
    
    def get_keywords_batch(self, products: List[Dict]) -> List[List[str]]:
        """
        Pobiera słowa kluczowe dla grupy produktów w jednym zapytaniu
        """
        prompt = self.create_batch_prompt(products)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Jesteś ekspertem od składników spożywczych. Odpowiadasz TYLKO w formacie JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            result = json.loads(response.choices[0].message.content)
            return result["keywords"]
            
        except Exception as e:
            print(f"Błąd API: {e}")
            # Fallback - puste słowa kluczowe
            return [[] for _ in products]
    
    def enhance_products_file(self, input_file: str, output_file: str = None, batch_size: int = 10):
        """
        Główna funkcja - wczytuje JSON, dodaje keywords, zapisuje
        """
        # Sprawdź czy plik wejściowy istnieje
        if not Path(input_file).exists():
            print(f"❌ Plik wejściowy nie istnieje: {input_file}")
            return None
        
        # Wczytaj dane
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Błąd wczytywania pliku: {e}")
            return None
        
        if 'products' not in data:
            print("❌ Brak klucza 'products' w danych")
            return None
        
        products = data['products']
        total_products = len(products)
        
        if total_products == 0:
            print("⚠️ Brak produktów do przetworzenia")
            return input_file
        
        print(f"🔄 Przetwarzanie {total_products} produktów w batchach po {batch_size}...")
        
        # Przetwarzaj w batchach
        processed = 0
        for i in range(0, total_products, batch_size):
            batch = products[i:i+batch_size]
            batch_num = i//batch_size + 1
            batch_end = min(i+batch_size, total_products)
            
            print(f"📦 Batch {batch_num}: produkty {i+1}-{batch_end}")
            
            # Pobierz keywords dla batcha
            keywords_list = self.get_keywords_batch(batch)
            
            # Dodaj keywords do produktów
            for j, keywords in enumerate(keywords_list):
                if i+j < len(products):
                    products[i+j]['english_keywords'] = keywords
                    processed += 1
            
            print(f"   ✅ Przetworzono {len(keywords_list)} produktów")
            
            # Krótka pauza żeby nie spamować API
            if i + batch_size < total_products:  # Nie czekaj po ostatnim batchu
                time.sleep(1)
        
        # Zapisz wynik
        if output_file is None:
            output_file = input_file.replace('.json', '_enhanced.json')
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Zapisano {processed} rozszerzonych produktów do: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"❌ Błąd zapisu pliku: {e}")
            return None

def main():
    """Główna funkcja uruchamiająca enhancement"""
    print("🤖 Uruchamiam LLM Enhancer dla produktów Biedronki...")
    
    # Pobierz API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Brak OPENAI_API_KEY w zmiennych środowiskowych")
        sys.exit(1)
    
    # Ścieżki plików
    input_file = "/shared/biedronka_offers.json"
    output_file = "/shared/biedronka_offers_enhanced.json"
    
    # Sprawdź czy plik wejściowy istnieje
    if not Path(input_file).exists():
        print(f"❌ Plik wejściowy nie istnieje: {input_file}")
        sys.exit(1)
    
    # Utwórz enhancer i uruchom
    try:
        enhancer = ProductKeywordsEnhancer(api_key)
        result = enhancer.enhance_products_file(
            input_file=input_file,
            output_file=output_file,
            batch_size=8  # Mniejsze batche = mniej błędów API
        )
        
        if result:
            print("🎉 Enhancement zakończony pomyślnie!")
            
            # Pokaż przykład rezultatu
            with open(result, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            enhanced_count = sum(1 for p in data['products'] if 'english_keywords' in p and p['english_keywords'])
            print(f"📊 Statystyki: {enhanced_count}/{len(data['products'])} produktów ma keywords")
            
            # Pokaż kilka przykładów
            print("\n🎯 PRZYKŁADY REZULTATÓW:")
            examples = [p for p in data['products'] if 'english_keywords' in p and p['english_keywords']][:3]
            for product in examples:
                print(f"• {product['name']} → {', '.join(product['english_keywords'])}")
        else:
            print("❌ Enhancement nie powiódł się")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 Nieoczekiwany błąd: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()