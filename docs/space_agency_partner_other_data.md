# Space Agency Partner & Other Data

Inventory of resources used in Harmonized Heat Neiva, reviewed against the repository on November 15, 2026. The following English descriptions can be used in the Space Apps submission. Enter the resource name in **Link Text** and its full URL in **Link**.

## Other data, imagery and geographic resources

| Link Text | Link | Use in the project |
|---|---|---|
| geoBoundaries gbOpen | [https://www.geoboundaries.org/](https://www.geoboundaries.org/) | Global administrative boundaries, requested by country and administrative level. Original sources and license metadata are retained. |
| DANE — Colombia municipal boundaries via geoBoundaries | [https://www.geoboundaries.org/api/current/gbOpen/COL/ADM2/](https://www.geoboundaries.org/api/current/gbOpen/COL/ADM2/) | Colombia ADM2, original source DANE (2020), CC BY 4.0. The offline Huila municipalities and their dissolved department boundary derive from this dataset. |
| Natural Earth | [https://www.naturalearthdata.com/](https://www.naturalearthdata.com/) | Public-domain country outlines, country index, global rivers and lakes, and Colombian urban-area context. Data prepared from the v5.1.2 GeoJSON distribution. |
| Natural Earth vector data v5.1.2 | [https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson](https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson) | Reproducible source files for the local geographic layers. |
| OpenStreetMap contributors | [https://www.openstreetmap.org/copyright](https://www.openstreetmap.org/copyright) | Roads/infrastructure tiles, place-search data and detailed global waterways. Data are licensed under ODbL; attribution is displayed. |
| Nominatim | [https://nominatim.org/](https://nominatim.org/) | User-triggered search for countries, cities, neighborhoods and addresses using OpenStreetMap data. |
| OpenFreeMap | [https://openfreemap.org/](https://openfreemap.org/) | Public vector-tile service for detailed worldwide rivers, streams, canals and water bodies as the user zooms in. |
| OpenMapTiles | [https://www.openmaptiles.org/](https://www.openmaptiles.org/) | Vector-tile schema used by the OpenFreeMap water and waterway layers. |
| Open-Meteo Historical Weather API | [https://open-meteo.com/en/docs/historical-weather-api](https://open-meteo.com/en/docs/historical-weather-api) | Optional temperature, humidity, rainfall and wind context. Modeled historical weather, not station observations. |
| Copernicus Climate Change Service — ERA5 / ECMWF | [https://climate.copernicus.eu/climate-reanalysis](https://climate.copernicus.eu/climate-reanalysis) | Reanalysis provenance for the Open-Meteo historical service, which combines ERA5, ERA5-Land and ECMWF IFS according to date and coverage. No separate Copernicus download is performed by this application. |
| ASTER GDEM V003 — NASA/METI/AIST/Japan Spacesystems and U.S./Japan ASTER Science Team | [https://catalog.data.gov/dataset/aster-global-digital-elevation-model-v003](https://catalog.data.gov/dataset/aster-global-digital-elevation-model-v003) | Joint U.S./Japan elevation product underlying the optional shaded-relief layer delivered through NASA GIBS. |

Natural Earth terms: [https://www.naturalearthdata.com/about/terms-of-use/](https://www.naturalearthdata.com/about/terms-of-use/). Open-Meteo data attribution and CC BY 4.0: [https://open-meteo.com/en/licence](https://open-meteo.com/en/licence). Public service use also follows the Nominatim and OpenStreetMap tile policies: [https://operations.osmfoundation.org/policies/nominatim/](https://operations.osmfoundation.org/policies/nominatim/) and [https://operations.osmfoundation.org/policies/tiles/](https://operations.osmfoundation.org/policies/tiles/).

## Code, documentation and development tools

| Link Text | Link | Use |
|---|---|---|
| MapLibre GL JS | [https://maplibre.org/maplibre-gl-js/docs/](https://maplibre.org/maplibre-gl-js/docs/) | Current WebGL globe, map rendering and geographic layers. Bundled locally with its copyright and license notices. |
| Leaflet | [https://leafletjs.com/](https://leafletjs.com/) | Earlier regional-map implementation; legacy vendor code remains in the repository with its BSD license. The current globe uses MapLibre. |
| Python | [https://www.python.org/](https://www.python.org/) | Ingestion, harmonization, API and data-preparation scripts. |
| FastAPI | [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/) | HTTP API and validation. |
| Uvicorn | [https://github.com/Kludex/uvicorn](https://github.com/Kludex/uvicorn) | ASGI server. |
| DuckDB | [https://duckdb.org/](https://duckdb.org/) | Analytical queries and harmonization. |
| Apache Arrow / PyArrow | [https://arrow.apache.org/docs/python/](https://arrow.apache.org/docs/python/) | Columnar data and Parquet files. |
| cryptography / Fernet | [https://cryptography.io/en/latest/fernet/](https://cryptography.io/en/latest/fernet/) | Authenticated encryption of the server-side FIRMS credential. |
| tzdata | [https://pypi.org/project/tzdata/](https://pypi.org/project/tzdata/) | Time-zone database distribution. |
| uv | [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/) | Python environment, dependency management and reproducible lock file. |
| Hatchling | [https://hatch.pypa.io/latest/](https://hatch.pypa.io/latest/) | Python package build backend. |
| pytest | [https://docs.pytest.org/en/stable/](https://docs.pytest.org/en/stable/) | Automated tests. |
| HTTPX | [https://www.python-httpx.org/](https://www.python-httpx.org/) | HTTP/API testing. |
| Node.js | [https://nodejs.org/en](https://nodejs.org/en) | Browser-verification scripts and JavaScript checks. |
| Google Chrome / Chrome DevTools Protocol | [https://chromedevtools.github.io/devtools-protocol/](https://chromedevtools.github.io/devtools-protocol/) | Browser automation, visual inspection and project screenshots. |
| Git | [https://git-scm.com/](https://git-scm.com/) | Version control. |
| GitHub Actions | [https://github.com/features/actions](https://github.com/features/actions) | Automated verification and deployment workflow. |
| GitHub Pages | [https://docs.github.com/en/pages](https://docs.github.com/en/pages) | Hosting of the static synthetic demonstration. |
| Vercel | [https://vercel.com/docs](https://vercel.com/docs) | Hosting of the Python application and browser interface. |
| OpenAI Codex | [https://openai.com/codex/](https://openai.com/codex/) | AI assistance with coding, debugging, translation, documentation and validation during development. It does not supply the scientific observations. |

MapLibre's bundled notice also credits earlier Mapbox GL JS code, glfx.js and d3-color. Upstream resources: [https://github.com/mapbox/mapbox-gl-js/tree/v1.13.0](https://github.com/mapbox/mapbox-gl-js/tree/v1.13.0), [https://github.com/evanw/glfx.js](https://github.com/evanw/glfx.js) and [https://github.com/d3/d3-color](https://github.com/d3/d3-color). These are embedded dependencies, not additional map services.

Dependency versions and transitive Python packages are recorded in `uv.lock`; the direct runtime, test and build dependencies are declared in `pyproject.toml`. Their own upstream copyright notices and licenses apply.

Additional Python packages resolved in the lock file (including platform-specific and testing dependencies):

| Link Text | Link |
|---|---|
| annotated-doc | [https://pypi.org/project/annotated-doc/](https://pypi.org/project/annotated-doc/) |
| annotated-types | [https://pypi.org/project/annotated-types/](https://pypi.org/project/annotated-types/) |
| AnyIO | [https://pypi.org/project/anyio/](https://pypi.org/project/anyio/) |
| certifi | [https://pypi.org/project/certifi/](https://pypi.org/project/certifi/) |
| CFFI | [https://pypi.org/project/cffi/](https://pypi.org/project/cffi/) |
| Click | [https://pypi.org/project/click/](https://pypi.org/project/click/) |
| Colorama | [https://pypi.org/project/colorama/](https://pypi.org/project/colorama/) |
| h11 | [https://pypi.org/project/h11/](https://pypi.org/project/h11/) |
| HTTPCore | [https://pypi.org/project/httpcore/](https://pypi.org/project/httpcore/) |
| idna | [https://pypi.org/project/idna/](https://pypi.org/project/idna/) |
| iniconfig | [https://pypi.org/project/iniconfig/](https://pypi.org/project/iniconfig/) |
| OpenTelemetry API | [https://pypi.org/project/opentelemetry-api/](https://pypi.org/project/opentelemetry-api/) |
| packaging | [https://pypi.org/project/packaging/](https://pypi.org/project/packaging/) |
| pluggy | [https://pypi.org/project/pluggy/](https://pypi.org/project/pluggy/) |
| pycparser | [https://pypi.org/project/pycparser/](https://pypi.org/project/pycparser/) |
| Pydantic | [https://pypi.org/project/pydantic/](https://pypi.org/project/pydantic/) |
| pydantic-core | [https://pypi.org/project/pydantic-core/](https://pypi.org/project/pydantic-core/) |
| Pygments | [https://pypi.org/project/pygments/](https://pypi.org/project/pygments/) |
| Starlette | [https://pypi.org/project/starlette/](https://pypi.org/project/starlette/) |
| typing-extensions | [https://pypi.org/project/typing-extensions/](https://pypi.org/project/typing-extensions/) |
| typing-inspection | [https://pypi.org/project/typing-inspection/](https://pypi.org/project/typing-inspection/) |

## Text, images and scientific references

The globe imagery is NASA GIBS imagery, including Blue Marble and ASTER-derived relief. Project screenshots show the application and preserve source attribution; they are not an independent satellite dataset. Interface icons are inline SVG drawings in the project, and typography uses system fonts. The scientific acknowledgements, warnings and references are recorded in `docs/cita.md`.

Bibliographic resources used by the explanatory documentation; these are not additional ingested datasets:

| Link Text | Link |
|---|---|
| Runfola et al. (2020) — geoBoundaries: A global database of political administrative boundaries | [https://doi.org/10.1371/journal.pone.0231866](https://doi.org/10.1371/journal.pone.0231866) |
| Justice et al. (2002) — The MODIS fire products | [https://www.sciencedirect.com/science/article/abs/pii/S0034425702000767](https://www.sciencedirect.com/science/article/abs/pii/S0034425702000767) |
| Morisette et al. (2005) — Validation of the MODIS active fire product over Southern Africa with ASTER data | [https://www.tandfonline.com/doi/abs/10.1080/01431160500113526](https://www.tandfonline.com/doi/abs/10.1080/01431160500113526) |
| Morisette et al. (2005) — Validation of MODIS Active Fire Detection Products Derived from Two Algorithms | [https://journals.ametsoc.org/view/journals/eint/9/9/ei141.1.xml](https://journals.ametsoc.org/view/journals/eint/9/9/ei141.1.xml) |
| Csiszar et al. (2006) — Validation of active fire detection from moderate-resolution satellite sensors: the MODIS example in Northern Eurasia | [https://dataserver-coids.inpe.br/queimadas/queimadas/Publicacoes-Impacto/material3os/2006_Csiszar_etal_Validation_IEEE_DE3os.pdf](https://dataserver-coids.inpe.br/queimadas/queimadas/Publicacoes-Impacto/material3os/2006_Csiszar_etal_Validation_IEEE_DE3os.pdf) |
| Csiszar et al. (2014) — Active fires from the Suomi NPP Visible Infrared Imaging Radiometer Suite | [https://directreadout.sci.gsfc.nasa.gov/publications_documents/Csiszar_et_al_2014_JGR.pdf](https://directreadout.sci.gsfc.nasa.gov/publications_documents/Csiszar_et_al_2014_JGR.pdf) |
| Schroeder et al. (2014) — The New VIIRS 375 m active fire detection data product | [https://directreadout.sci.gsfc.nasa.gov/publications_documents/Schroeder_et_al_2014b_RSE.pdf](https://directreadout.sci.gsfc.nasa.gov/publications_documents/Schroeder_et_al_2014b_RSE.pdf) |

NASA resources, to also declare in the NASA-data field:

| Link Text | Link |
|---|---|
| NASA FIRMS — MODIS and VIIRS thermal detections, LANCE / ESDIS | [https://www.earthdata.nasa.gov/data/tools/firms](https://www.earthdata.nasa.gov/data/tools/firms) |
| NASA GIBS — Blue Marble, imagery and shaded relief | [https://www.earthdata.nasa.gov/data/tools/gibs](https://www.earthdata.nasa.gov/data/tools/gibs) |
| NASA FIRMS documentation, acknowledgements and scientific references | [https://www.earthdata.nasa.gov/data/tools/firms/faq](https://www.earthdata.nasa.gov/data/tools/firms/faq) |

Sources evaluated only as possible extensions, such as Meteomatics, Microsoft Planetary Computer, Sentinel-3 FRP and Esri/IO land cover, are not active project integrations. Their evaluation is documented separately in `docs/fuentes_complementarias.md`.

This inventory identifies actual sources and the permissions stated by their providers; it does not assign a new license to third-party material or claim endorsement by an agency. Keep data attribution, upstream software notices and any applicable share-alike conditions when publishing or redistributing the project.
