# TechnologieGeneratywne
Projekt mgr sem1

Uruchomienie
```
docker-compose up -d
```

trzeba dodac .env z api do openai w katalogu projektu

Frontend:
```
http://localhost:8501/
```

Plik requirements.txt jest potrzebny jedynie na potrzeby venva do uruchamiania notatników

scraper/enhancer.py - to taki agent jeśli mogę go tak nazwać - bierze zescrapowane produkty i z użyciem LLM dodaje angielskie słowa kluczowe, dzięki którym łatwiej później wyszukiwać pasujące przepisy

scraper-1  | 🎯 PRZYKŁADY REZULTATÓW:

scraper-1  | • Kiełbasa Podwawelska Kraina Wędlin → sausage, meat, pork, deli

scraper-1  | • Szynka Kraina Wędlin, 100 g → ham, meat, deli, sliced

scraper-1  | • Boczek Kraina Wędlin, 100 g → bacon, meat, pork, fat


TODO: Przyda się jakiś scheduler, który uruchomi scraping plus tłumaczenia wraz z uruchomieniem kontenerów a potem będzie uruchamiać to codziennie np o 3:00 AM. Być może enhancer nie powinien być w folderze scraper, tylko AI (po prostu jakoś to uporządkować i skonteneryzować poprawnie)

W folderze embedder znajduje się notatnik, który tworzy embeddingi dla przepisów umieszcoznych w /datatests - niedostępnych na github (kilka sample przepisów wrzucone w json) To jest do wykonania tylko raz, potem sobie korzystamy z tych embeddingów

![Alt text](Images/1.jpg?raw=true "1")
![Alt text](Images/2.jpg?raw=true "2")
![Alt text](Images/3.jpg?raw=true "3")
![Alt text](Images/4.jpg?raw=true "4")