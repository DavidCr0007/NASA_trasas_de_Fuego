# Harmonized Heat Neiva

[Español](README.md) · [English](README.en.md) · **Français**

Projet NASA Space Apps 2026 explorant les détections thermiques MODIS et VIIRS de NASA FIRMS, avec un globe, des limites locales et des calendriers d’activité harmonisés. Une détection n’est pas un incendie confirmé. **Ne pas utiliser cet outil pour protéger des vies ou des biens.**

## Démarrer localement

Utiliser PowerShell à la racine du dépôt. Installer Python et les dépendances avec uv :

```powershell
uv python install 3.13
uv sync --locked
```

Créer et démarrer une démonstration synthétique :

```powershell
uv run python tools/generar_historico.py data/sample_historica
uv run python -m harmonize.pipeline --input data/sample_historica --output data/processed/demo_historica
uv run python -m api --datos data/processed/demo_historica --puerto 8000
```

Ouvrir **http://127.0.0.1:8000/ui/**. Choisir **Langue → Français**. L’application propose également l’espagnol et l’anglais, ainsi que des liens directs comme `/ui/?lang=fr`. La préférence est mémorisée sans recréer la carte ni modifier les données scientifiques.

## Clé FIRMS chiffrée et données réelles sur Vercel

Le fichier local `.env` est privé et n’est pas transmis à Vercel. La clé est utilisée uniquement par le serveur Python. Pour chiffrer une valeur `FIRMS_MAP_KEY` déjà saisie dans le fichier local :

```powershell
uv run python tools/cifrar_clave_firms.py --archivo .env
```

L’outil remplace la valeur en clair par `FIRMS_MAP_KEY_ENCRYPTED` et `FIRMS_SECRET_KEY`, au moyen du chiffrement authentifié Fernet. Il n’imprime pas leurs valeurs. La clé de déchiffrement doit également rester privée.

Dans Vercel **Project → Settings → Environment Variables**, configurer pour **Production** :

| Nom | Type | Valeur |
|---|---|---|
| `FIRMS_MAP_KEY_ENCRYPTED` | Secret | Copier sa valeur depuis le fichier privé `.env`. |
| `FIRMS_SECRET_KEY` | Secret | Copier sa valeur depuis `.env`. |
| `HHN_MODO_DATOS` | Config | `firms` |
| `FIRMS_NRT_DIAS` | Config | `7` recommandé et par défaut ; valeurs de `1` à `10`, téléchargées par fenêtres de 5 jours maximum. |

Laisser `HHN_DATOS` non défini pour utiliser le jeu réel construit dans ce mode. Un chemin personnalisé est prioritaire. Publier les changements puis redéployer après la configuration. La construction télécharge MODIS NRT, VIIRS NOAA-20 NRT et VIIRS NOAA-21 NRT pour les derniers jours UTC complets configurés, puis exécute le traitement d’harmonisation.

Si Production contient déjà `FIRMS_NRT_DIAS=1`, remplacer la valeur par `7` et redéployer. Une archive d’un seul jour ne peut pas fournir des observations différentes pour 1, 2 et 7 jours. L’interface indique désormais la couverture, désactive les périodes indisponibles et synchronise calendrier, intervalle de dates, globe et détail régional.

Le mode réel échoue explicitement si la configuration ou l’ingestion échoue ; il ne remplace pas silencieusement les observations par des données synthétiques. `HHN_MODO_DATOS=demo` conserve volontairement la démonstration synthétique. Les données réelles constituent un instantané du déploiement ; une reconstruction actualise la période. Les observations NRT restent préliminaires.

Ouvrir **Vérifier les données et la méthode** ou `/estado-servicios` pour consulter l’état de connexion sans secrets. Cet endpoint indique si la clé est configurée et chiffrée, le mode du jeu actif et les dates d’ingestion. Il ne retourne jamais les identifiants secrets. Une clé configurée ne modifie pas à elle seule un jeu synthétique déjà construit.

Pour un jeu réel déjà traité localement :

```powershell
uv run python -m api --datos data/processed/vercel_firms --puerto 8000
```

## Méthode, provenance et limites

La recherche distingue les pays et les communes homonymes. Vérifiez la catégorie et le lieu complet, puis choisissez **Confirmer ce lieu** pour déplacer la carte. **Colombia** présente le pays en premier et la commune du Huila séparément ; **Colombia, Huila** limite la correspondance locale à la commune.

Inventaire des ressources pour la soumission : [Space Agency Partner & Other Data](docs/space_agency_partner_other_data.md). La couche hydrographique couvre désormais le monde avec Natural Earth et les cours d’eau détaillés OpenStreetMap/OpenFreeMap dès le zoom 6, selon la cartographie disponible et l’accès à internet.

Version des règles : `armonizacion-0.3.1`. Indicateur par défaut : cellules actives équivalentes, `celdas-eq-1.1.0` ; il ne s’agit pas de la somme des pixels MODIS et VIIRS. Les fichiers sources, sommes de contrôle, dates d’acquisition et de téléchargement, règles et identifiants des jeux restent traçables dans JSON, CSV et les fiches. Les noms des champs de l’API restent identiques dans les trois langues.

Consulter `/metodologia?idioma=fr`, `/limitaciones?idioma=fr` et `/procedencia`. La référence utilise le 95e percentile historique dans une fenêtre de ±7 jours, exclut l’année évaluée et exige cinq années de référence. Les données NRT récentes sans historique suffisant ne permettent pas de calculer les seuils des jours inhabituels. Les lacunes de couverture, les zéros, l’étalonnage empirique, l’emprise des pixels et la saturation de la température de brillance restent des limites ; l’exactitude scientifique n’est pas certifiée.

## Vérifier

```powershell
uv run pytest -q
uv run python tools/scan_secrets.py
node tools/prueba_navegador.mjs http://127.0.0.1:8000/ui/ docs/capturas/langues "C:/Program Files/Google/Chrome/Application/chrome.exe" idiomas
```

Le parcours navigateur nécessite Node.js et Chrome. Les images NASA, limites distantes, données météo et recherches distantes nécessitent internet ; les données synthétiques et les limites locales restent disponibles localement. La démonstration GitHub Pages n’a pas de serveur Python et ne peut pas utiliser un secret FIRMS de production.

Sources : NASA FIRMS (LANCE / ESDIS), NASA GIBS, geoBoundaries/DANE, Natural Earth, OpenStreetMap/Nominatim et Open-Meteo. Les attributions et avertissements scientifiques restent visibles dans l’application.
