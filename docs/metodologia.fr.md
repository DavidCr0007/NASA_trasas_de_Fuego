# Méthodologie d’harmonisation

Harmonized Heat Neiva · règles `armonizacion-0.3.1` · indicateur `celdas-eq-1.1.0`.

## Données et provenance

Les détections NASA FIRMS MODIS C6.1 et VIIRS 375 m conservent le produit, la collection, la plateforme, l’acquisition UTC, la confiance, la FRP, la température de brillance, le fichier source, son SHA-256, la date de téléchargement et le numéro d’enregistrement CSV. Les observations en temps quasi réel (NRT) sont préliminaires. La qualité standard et les données synthétiques restent explicitement identifiées.

`/procedencia` décrit séparément les jeux de l’analyse et du globe. Les réponses et CSV portent un identifiant reproductible du jeu. Ce linéage déclaré ne constitue pas une certification scientifique indépendante. Le numéro d’enregistrement commence à 1 après l’en-tête CSV ; ce n’est pas nécessairement une ligne physique si des champs sont multilignes.

## Règles de traitement

1. **R1 : grille.** Les détections utilisent une grille fixe de 0,009° en coordonnées géographiques, d’origine latitude −90°, longitude −180°. Une cellule mesure environ 1 km près de la zone de référence. Sa largeur physique varie avec la latitude ; les cellules ne sont pas de surface égale.
2. **R2 : confiance.** Les valeurs MODIS sont classées en confiance faible, nominale et élevée selon les seuils provisoires 30 et 80. Les classes VIIRS sont normalisées. La confiance n’est pas une incertitude de température.
3. **R3 : déduplication.** Les détections d’une même cellule sont regroupées dans les trois heures suivant une ancre initiale, avec ordre et représentant déterministes. La relation n’est pas transitive. Des observations du même capteur ou de capteurs différents peuvent fusionner. Les enregistrements absorbés sont conservés dans une table distincte avec l’identifiant du représentant.
4. **R4 : traçabilité.** Les fichiers bruts sont immuables et enregistrés avec leur SHA-256. Les lignes invalides sont mises en quarantaine avec leur motif. Aucun enregistrement n’est supprimé silencieusement : entrées = représentants + doublons + quarantaine.
5. **Agrégation.** Les tables cellule-jour conservent les comptages de représentants, d’observations originales et de capteurs ainsi que les statistiques FRP. Chaque observation originale reste associée à son propre jour UTC, même si son représentant appartient au jour voisin.

## Indicateur harmonisé

L’indicateur par défaut est le nombre de **cellules actives équivalentes**, plutôt que la somme des pixels MODIS et VIIRS. Il reconstruit les cellules quotidiennes distinctes à partir des représentants et des doublons.

La constellation de référence est MODIS (Terra et Aqua) ∪ Suomi NPP. Avant cette période, les cellules MODIS sont multipliées par des facteurs mensuels estimés sur le chevauchement. Après Suomi NPP, les cellules MODIS ∪ NOAA-20 sont divisées par leur facteur de chevauchement. Ces facteurs sont estimés dans le jeu traité, publiés par l’API et restent des hypothèses empiriques.

Si les observations de référence Suomi NPP sont absentes, la méthode est indiquée **non étalonnée** et compte les cellules actives de toutes les constellations disponibles. Cela ne garantit pas la comparabilité interannuelle. `metrica=n_brutas` demande explicitement les comptages originaux.

## R5 : référence et jours inhabituels

Le seuil par défaut est le 95e percentile historique pour le même jour de l’année dans une fenêtre de ±7 jours, en excluant l’année évaluée. Au moins cinq années de référence sont nécessaires pour un seuil journalier. Si la référence est insuffisante, le seuil et la classification restent nuls.

La couverture s’étend de la première à la dernière date de détection du jeu. Les lacunes internes sont remplies par zéro. Il ne s’agit pas d’un masque d’observations satellitaires valides, de nuages ou de disponibilité des capteurs ; zéro détection ne prouve pas l’absence de feu. Les années partielles et les références dominées par des zéros demandent une validation supplémentaire. Un jour inhabituel est une comparaison statistique, pas une alerte d’urgence.

## Définitions spatiales et interprétation

Pour les polygones administratifs pris en charge, les cellules sont sélectionnées selon l’appartenance de leur centre au polygone. Les requêtes rectangulaires utilisent leurs quatre coordonnées. La carte positionne les détections à leurs coordonnées. Les petits écarts aux limites doivent être interprétés selon ces définitions. Les cercles mondiaux regroupent les détections : couleur selon la FRP maximale, taille selon le nombre ; ils ne représentent pas la surface brûlée.

La FRP est exprimée en MW et ne se convertit pas directement en °C. La température de brillance disponible est convertie selon °C = K − 273,15. Elle mélange les signaux du feu et de l’environnement ; ce n’est pas la température de la flamme ni celle de l’air. Les résolutions nominales MODIS et VIIRS sont de 1 000 m et 375 m ; les pixels s’agrandissent vers le bord du balayage. Le fichier ne fournit pas d’incertitude individuelle de ±°C.

## Reproduction et vérification

Avec les dépendances fixées dans `uv.lock` :

```powershell
uv run python -m harmonize.pipeline --input data/sample --output data/processed/demo
uv run pytest -q
uv run python tools/auditar_plataforma.py --datos data/processed/global_nrt --crudos data/raw/global --salida docs/evidencias/check.json
```

Les schémas, l’ordre des lignes et les paramètres Parquet déterministes rendent les mêmes entrées et la même configuration reproductibles avec les mêmes dépendances. `/procedencia` publie des sommes de contrôle déclarées ; l’outil d’audit vérifie les fichiers locaux et compare JSON et CSV. Les tests synthétiques vérifient l’exécution et la cohérence, pas l’exactitude empirique des observations.

Sources : NASA FIRMS (LANCE / ESDIS). Voir `/limitaciones?idioma=fr` pour les incertitudes restantes. Ne pas utiliser cet outil pour protéger des vies ou des biens.
