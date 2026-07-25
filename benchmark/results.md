# Benchmark Proof Engine — metriche di successo

Casi totali: 8
Detection rate (bug individuato dal mutation testing): 100%
Mutation score medio: 44%

| Caso | Categoria | Verdetto | Mutation score | Bug rilevato | Durata (s) |
|---|---|---|---|---|---|
| eta_maggiorenne | boundary | pass | 67% | si | 1.97 |
| password_minima | off_by_one | warn | 0% | si | 0.82 |
| checkout_carrello | logica_booleana | pass | 80% | si | 1.68 |
| sconto_importo_negativo | early_return | warn | 50% | si | 1.90 |
| prime_parole | slice | pass | 67% | si | 1.12 |
| cache_scarta | chiamata_mancante | warn | 0% | si | 0.48 |
| prezzo_iva | aritmetica | warn | 50% | si | 0.73 |
| tentativi_login | default_sbagliato | warn | 40% | si | 1.44 |
