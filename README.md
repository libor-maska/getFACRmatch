# getFACRmatch

Vypíše všechny hráče z oficiálního zápisu o utkání na [is.fotbal.cz](https://is.fotbal.cz) (informační systém FAČR). Stačí zadat číslo utkání.

Pro každého hráče vypíše **příjmení, jméno, FAČR ID a číslo dresu**. Nejdřív jsou domácí, potom hosté. Výsledek se dá uložit i do CSV.

## Ukázka

```
python program.py <číslo utkání>
```

```
== Domácí: <název domácího týmu> ==
Příjmení               Jméno          FAČR ID   Dres
Novák                  Jan            XXXXXXXX     1
Svoboda                Petr           XXXXXXXX     2
...

== Hosté: <název hostujícího týmu> ==
Příjmení               Jméno          FAČR ID   Dres
Dvořák                 Tomáš          XXXXXXXX     1
...
```


## Instalace

Python 3

Knihovny:

```bash
pip install -r requirements.txt
```

## Použití

Výpis hráčů do terminálu:

```bash
python program.py <číslo utkání>
```

Uložení do CSV. Soubor má kódování UTF-8 s BOM.
V Excelu se správně zobrazí čeština.

```bash
python program.py <číslo utkání> --csv hraci.csv
```

CSV má sloupce `strana, tym, prijmeni, jmeno, id, dres`.

### Kde najdu číslo utkání?

Číslo utkání je v zápisu o utkání nebo v detailu zápasu na is.fotbal.cz. Má 14 znaků ve tvaru `RRRRSSSSSSKKZZ`:

| Část | Význam |
|---|---|
| `RRRRSSSSSS` (10 znaků) | ročník + číslo soutěže |
| `KK` (2 číslice) | kolo |
| `ZZ` (2 číslice) | pořadí zápasu v kole |


## Omezení

- Zápis uvádí hráče jako „Příjmení Jméno“. Za jméno se bere poslední slovo a zbytek je příjmení.
- Hráče jde vypsat jen ze zápasů, které už mají zápis.
- Program je určený k osobnímu použití.
