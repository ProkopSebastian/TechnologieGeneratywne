RAG creating recipies based on https://www.kaggle.com/datasets/hugodarwood/epirecipes

gets ../shared_data/biedronka_offers

to use creade .dotenv inside AI folder and populate with key (OPENAI_API_KEY=)

TODO
pull data using kagle
add docker (python 3.11)
add flash
better code quality(classes) and readability
need to trucate recipies to meet token limit

EDIT
removed https://www.kaggle.com/datasets/hugodarwood/epirecipes - too many tokens
only based on biedronka offers

This is simple rag that embeds biedronka offers

simple question:
```
```

```
Answer: To determine the best deal, let's analyze the offers based on their discounts and prices:

1. **Filet z piersi kurczaka**:
   - Price: Not specified
   - Discount: 70% off on the second product
   - [Product Link](https://www.biedronka.pl/pl/product,id,438769,name,swiezy-filet-z-piersi-kurczaka-pakowany-prozniowo-kraina-mies-mega-paka)

2. **Szynka wieprzowa bez kości**:
   - Price: 7,99 PLN/kg
   - Discount: 57% off
   - [Product Link](https://www.biedronka.pl/pl/product,id,438770,name,szynka-wieprzowa-bez-kosci-pakowana-prozniowo-kraina-mies)

3. **Mięso mielone z łopatki wieprzowej**:
   - Price: 5,49 PLN for 500 g
   - Discount: 50% off (1+1 GRATIS)
   - [Product Link](https://www.biedronka.pl/pl/product,id,438771,name,mieso-mielone-z-lopatki-wieprzowej-kraina-mies-500-g)

4. **Udo lub podudzie z kurczaka**:
   - Price: 7,99 PLN/kg
   - Discount: 36% off

5. **Mięso w słoiku**:
   - Price: 5,99 PLN for 280 g
   - Discount: 64% off on the second product
   - [Product Link](https://www.biedronka.pl/pl/product,id,438411,name,mieso-w-sloiku-kraina-wedlin-280-g)

### Best Deal Analysis:
- The **Mięso mielone z łopatki wieprzowej** at 5,49 PLN for 500 g with a 50% discount (1+1 GRATIS) effectively gives you two for the price of one, making it a great deal.
- The **Mięso w słoiku** offers a significant discount of 64% on the second product, but the price is higher per unit weight compared to the minced meat.
- The **Filet z piersi kurczaka** has a 70% discount on the second product, but the price is not specified, making it hard to evaluate.      

### Conclusion:
The **Mięso mielone z łopatki wieprzowej** (5,49 PLN for 500 g with 1+1 GRATIS) is the best deal based on the available information, as it provides the best value for money with a clear price and significant discount.
```