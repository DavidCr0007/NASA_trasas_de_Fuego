# ADR 0006: Stack tecnológico

## Estado

ACEPTADA (H0).

## Contexto

El proyecto necesita leer CSV de FIRMS, validarlos, agregarlos por celda y día, guardar resultados reproducibles y, más adelante, exponerlos por una API. El equipo debe poder reproducir el entorno y verificar el hash de las salidas (D-06).

## Decisión

- **Python 3.13** como lenguaje principal.
- **uv** para gestionar entorno y dependencias, con versiones fijadas en `uv.lock`.
- **pytest** para las pruebas.
- **Parquet con pyarrow** como almacén de salidas.
- **DuckDB** para consultas analíticas sobre los Parquet.
- **FastAPI** en una fase posterior (`src/api/`).
- **Make** como interfaz de comandos (`make sync`, `make test`, `make demo`, `make download`, `make secrets`).

## Alternativas

1. **pandas como almacén principal (CSV).** Sin tipos fuertes ni esquema, y menos reproducible en hash. Descartada.
2. **Poetry o pip con requirements.txt.** Menos control del lockfile y más lento. Descartada frente a uv.
3. **Base de datos relacional (PostgreSQL) desde el inicio.** Añade un servicio que no se necesita para H0–H2. Descartada.
4. **Otro lenguaje.** Descartada: el equipo ya trabaja con Python y el prototipo está en Python.

## Consecuencias

- Reproducibilidad: el hash del Parquet depende de `uv.lock`, en particular de la versión de `pyarrow` (véase `docs/limitaciones.md`).
- `uv sync` necesita red la primera vez.
- Los nombres de paquete genéricos (`api`, `ui`, `ingest`) pueden colisionar con otros paquetes; se revisará en el riesgo correspondiente (`tasks/RIESGOS.md`).

## Por confirmar

- Versión mínima de pyarrow que garantice el mismo hash entre máquinas.
- Si DuckDB se usa solo como motor de consulta o también para escribir Parquet.
