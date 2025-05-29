import requests
from bs4 import BeautifulSoup
import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
import time
from urllib.parse import urljoin, urlparse
import os
import logging
from datetime import datetime

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Product:
    name: str
    price: str
    original_price: Optional[str] = None
    discount_info: Optional[str] = None
    unit: Optional[str] = None
    promotion_type: Optional[str] = None
    product_url: Optional[str] = None
    image_url: Optional[str] = None

class BiedronkaScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.base_url = "https://www.biedronka.pl"
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Pobiera stronę i zwraca obiekt BeautifulSoup"""
        try:
            logger.info(f"Pobieranie: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Błąd podczas pobierania strony {url}: {e}")
            return None
    
    def extract_product_links(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Wyciąga linki do produktów ze strony głównej"""
        product_links = []
        
        # Szuka linków do produktów
        links = soup.find_all('a', href=re.compile(r'/pl/product,id,\d+'))
        
        for link in links:
            href = link.get('href')
            title = link.get('title', '')
            
            # Sprawdza czy link ma obrazek (oznacza że to główny link produktu)
            img = link.find('img')
            if img and href and title:
                product_links.append({
                    'url': urljoin(self.base_url, href),
                    'name': title.strip(),
                    'image_url': img.get('src', '') if img else ''
                })
        
        # Usuwa duplikaty
        seen_urls = set()
        unique_links = []
        for link in product_links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                unique_links.append(link)
        
        return unique_links
    
    def extract_price_from_product_page(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """Wyciąga informacje o cenie ze strony produktu"""
        price_info = {
            'price': None,
            'original_price': None,
            'discount_info': None,
            'unit': None,
            'promotion_type': None
        }
        
        # Szuka głównej ceny - najpierw próbuje konkretnych klas
        pln_elem = soup.select_one('.pln')
        gr_elem = soup.select_one('.gr')
        
        if pln_elem:
            pln_text = pln_elem.get_text().strip()
            if gr_elem:
                gr_text = gr_elem.get_text().strip()
                price_info['price'] = f"{pln_text},{gr_text}"
            else:
                price_info['price'] = pln_text
        
        # Fallback - szuka innych selektorów jeśli nie ma klas pln/gr
        if not price_info['price']:
            price_selectors = [
                '.price-wrapper .price',
                '.price-item .price',
                '.product-price .price',
                '[class*="price"]:not([class*="original"]):not([class*="old"])',
                '.price-current',
                '.current-price'
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    # Wyciąga cenę (liczby z przecinkami/kropkami i groszami)
                    price_match = re.search(r'(\d+[,.]?\d{0,2})', price_text)
                    if price_match:
                        price_info['price'] = price_match.group(1)
                        break
        
        # Alternatywna metoda - szuka w tekście
        if not price_info['price']:
            # Szuka wzorców cenowych w całym tekście
            text_content = soup.get_text()
            price_patterns = [
                r'(\d{1,3}[,.]?\d{0,2})\s*zł',
                r'cena[:\s]+(\d{1,3}[,.]?\d{0,2})',
                r'(\d{1,3}[,.]?\d{0,2})\s*/\s*(?:kg|szt|opak|l)',
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    price_info['price'] = match.group(1)
                    break
        
        # Szuka oryginalnej ceny
        original_price_selectors = [
            '.price-original',
            '.old-price',
            '.price-before',
            '[class*="original"]',
            '.crossed-price'
        ]
        
        for selector in original_price_selectors:
            orig_elem = soup.select_one(selector)
            if orig_elem:
                orig_text = orig_elem.get_text().strip()
                orig_match = re.search(r'(\d+[,.]?\d{0,2})', orig_text)
                if orig_match:
                    price_info['original_price'] = orig_match.group(1)
                    break
        
        # Szuka informacji o promocji
        promo_text = soup.get_text().lower()
        
        if 'gratis' in promo_text and ('1+1' in promo_text or 'drugi' in promo_text):
            price_info['promotion_type'] = '1+1 GRATIS'
        elif 'drugi' in promo_text and 'taniej' in promo_text:
            # Szuka procentu zniżki
            discount_match = re.search(r'drugi[^0-9]*(\d+)%[^a-z]*taniej', promo_text)
            if discount_match:
                price_info['promotion_type'] = f'Drugi {discount_match.group(1)}% taniej'
                price_info['discount_info'] = f'{discount_match.group(1)}% taniej na drugi produkt'
        elif 'supercena' in promo_text:
            price_info['promotion_type'] = 'SUPERCENA'
        
        # Szuka ogólnych zniżek
        discount_match = re.search(r'(\d+)%\s*taniej', promo_text)
        if discount_match and not price_info['discount_info']:
            price_info['discount_info'] = f'{discount_match.group(1)}% taniej'
        
        # Szuka jednostki
        unit_match = re.search(r'/\s*(kg|szt|opak|l|ml|g)\b', soup.get_text())
        if unit_match:
            price_info['unit'] = unit_match.group(1)
        
        return price_info
    
    def scrape_product_details(self, product_link: Dict[str, str]) -> Optional[Product]:
        """Scrapuje szczegóły pojedynczego produktu"""
        soup = self.fetch_page(product_link['url'])
        if not soup:
            return None
        
        # Wyciąga informacje o cenie
        price_info = self.extract_price_from_product_page(soup)
        
        # Tworzy obiekt produktu
        product = Product(
            name=product_link['name'],
            price=price_info['price'] or 'Sprawdź w sklepie',
            original_price=price_info['original_price'],
            discount_info=price_info['discount_info'],
            unit=price_info['unit'],
            promotion_type=price_info['promotion_type'],
            product_url=product_link['url'],
            image_url=product_link['image_url']
        )
        
        return product
    
    def scrape_offers(self, url: str, max_products: int = 20) -> List[Product]:
        """Główna metoda do scrapowania ofert"""
        logger.info(f"Scrapowanie ofert z: {url}")
        
        # Pobiera stronę główną
        soup = self.fetch_page(url)
        if not soup:
            return []
        
        # Wyciąga linki do produktów
        product_links = self.extract_product_links(soup)
        logger.info(f"Znaleziono {len(product_links)} linków do produktów")
        
        if not product_links:
            logger.warning("Nie znaleziono linków do produktów. Sprawdzam strukturę strony...")
            # Debug - pokazuje fragment HTML
            logger.debug("Pierwsze 1000 znaków HTML:")
            logger.debug(soup.prettify()[:1000])
            return []
        
        # Ogranicza liczbę produktów do sprawdzenia
        products_to_check = product_links[:max_products]
        logger.info(f"Sprawdzanie szczegółów dla {len(products_to_check)} produktów...")
        
        products = []
        for i, product_link in enumerate(products_to_check, 1):
            logger.info(f"Sprawdzanie produktu {i}/{len(products_to_check)}: {product_link['name']}")
            
            product = self.scrape_product_details(product_link)
            if product:
                products.append(product)
            
            # Przerwa między requestami
            time.sleep(1)
        
        logger.info(f"Pomyślnie wyciągnięto dane dla {len(products)} produktów")
        return products
    
    def save_to_json(self, products: List[Product], filepath: str = "/shared/biedronka_offers.json"):
        """Zapisuje produkty do pliku JSON"""
        products_dict = []
        for product in products:
            products_dict.append({
                'name': product.name,
                'price': product.price,
                'original_price': product.original_price,
                'discount_info': product.discount_info,
                'unit': product.unit,
                'promotion_type': product.promotion_type,
                'product_url': product.product_url,
                'image_url': product.image_url,
                'scraped_at': datetime.now().isoformat()
            })
        
        # Tworzy katalog jeśli nie istnieje
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'scraped_at': datetime.now().isoformat(),
                'total_products': len(products_dict),
                'products': products_dict
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Dane zapisane do pliku: {filepath}")
        return filepath

def main():
    """Główna funkcja programu - dla Dockera"""
    logger.info("=== BIEDRONKA SCRAPER START ===")
    
    scraper = BiedronkaScraper()
    
    # Konfiguracja z zmiennych środowiskowych
    url = os.getenv('SCRAPER_URL', "https://www.biedronka.pl/pl/oferta-z-karta-moja-biedronka")
    max_products = int(os.getenv('MAX_PRODUCTS', '20'))
    output_file = os.getenv('OUTPUT_FILE', '/shared/biedronka_offers.json')
    
    logger.info(f"URL: {url}")
    logger.info(f"Max produktów: {max_products}")
    logger.info(f"Plik wyjściowy: {output_file}")
    
    try:
        # Scrapuje oferty
        products = scraper.scrape_offers(url, max_products)
        
        if products:
            # Zapisuje do JSON
            saved_file = scraper.save_to_json(products, output_file)
            
            logger.info(f"SUKCES: Znaleziono {len(products)} produktów")
            logger.info(f"Dane zapisane do: {saved_file}")
            
            # Podsumowanie produktów z promocjami
            promo_products = [p for p in products if p.promotion_type or p.discount_info]
            logger.info(f"Produkty z promocjami: {len(promo_products)}")
            
        else:
            logger.error("Nie udało się wyciągnąć żadnych produktów")
            return 1
            
    except Exception as e:
        logger.error(f"Błąd podczas scrapowania: {e}")
        return 1
    
    logger.info("=== BIEDRONKA SCRAPER END ===")
    return 0

if __name__ == "__main__":
    exit(main())