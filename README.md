# Planificador de rutas óptimas – Metro CDMX (A*)

Aplicación web que calcula la ruta óptima entre dos estaciones del Metro de Ciudad de México (CDMX) utilizando el algoritmo de búsqueda A* (A-estrella).  
Forma parte de una práctica de la asignatura **Inteligencia Artificial (GCDIA)**.

La aplicación tiene en cuenta:

- Tiempos de viaje entre estaciones consecutivas.
- Tiempos de transbordo entre líneas.
- Horarios y frecuencias según el día de la semana.
- Información de accesibilidad (escaleras, escaleras mecánicas, ascensor).
- Visualización de la ruta sobre un mapa interactivo.

---

## 🚇 Funcionalidades principales

- **Planificación de ruta** entre dos estaciones del subconjunto de líneas del Metro CDMX definido en la práctica.
- **Cálculo de ruta con A***:
  - Función de coste `g(n)` basada en tiempo real (esperas + trayectos + transbordos).
  - Heurística `h(n)` basada en distancia geodésica (fórmula de Haversine).
- **Interfaz web** con:
  - Formularios para origen, destino, fecha y hora de salida.
  - Resumen de la ruta: duración total, hora estimada de llegada.
  - Lista ordenada de estaciones, líneas y transbordos.
  - Iconos de accesibilidad en las estaciones (♿, etc.).
- **Mapa interactivo**:
  - Visualización del recorrido completo sobre un mapa.
  - Marcadores por estación.
  - Polilínea que conecta las estaciones en orden.

---

## 🧠 Algoritmo y modelo

### Modelo de datos

- Datos de estaciones en `CDMX.csv`:
  - Nombre de estación.
  - Línea.
  - Latitud / longitud.
  - Orden en la línea (IDs).
  - Tiempo al siguiente y anterior.
  - Horarios de primera salida (laborable / sábado / domingo).
  - Frecuencias de paso.
  - Información de accesibilidad (escaleras, escaleras mecánicas, ascensor).

- Clase `Estacion` (en `cdmx.py`):
  - Encapsula todos los atributos relevantes.
  - Expone una propiedad de accesibilidad para facilitar su uso en las plantillas.

- Grafo:
  - Nodos: `(nombre_estación, línea)`.
  - Aristas:
    - Entre estaciones consecutivas de la misma línea (ida y vuelta).
    - Entre subestaciones del mismo nombre pero distinta línea (transbordos, coste fijo).

### Función de coste `g(n)`

`g(n)` modela el **tiempo total** (en minutos) desde el origen hasta el nodo `n`:

- Tiempo de espera hasta el siguiente tren:
  - Depende de la estación, la dirección, la hora actual y el día de la semana.
- Tiempo de viaje entre estaciones consecutivas:
  - Leído del CSV (`tiempo_sig`, `tiempo_ant`).
- Tiempo de transbordo:
  - Coste fijo (por ejemplo, 5 minutos) para cambiar de línea dentro de una estación.

### Heurística `h(n)`

Heurística **admisible** basada en la distancia:

- Distancia geodésica entre estación actual y destino (fórmula de Haversine).
- Conversión a tiempo suponiendo una velocidad máxima (p.ej. 50 km/h).
- Se expresa en minutos y se suma a `g(n)` para obtener `f(n) = g(n) + h(n)`.

---

## 🛠️ Tecnologías utilizadas

- **Backend**: Python 3, [Flask](https://flask.palletsprojects.com/)
- **Frontend**: HTML5, CSS3, Jinja2 (templates)
- **Mapas**: [Leaflet](https://leafletjs.com/) + tiles de OpenStreetMap/CARTO
- **Datos**: CSV (`CDMX.csv`)
- **Otros**: `csv`, `datetime`, `math`, `heapq` (librería estándar de Python)

---

## 📁 Estructura del repositorio

```text
.
├── cdmx.py             # Aplicación principal Flask (modelo, A*, rutas web)
├── CDMX.csv            # Datos de estaciones, tiempos, horarios y accesibilidad
├── templates/
│   ├── index.html      # Página de búsqueda (formulario)
│   └── results.html    # Página de resultados (ruta + mapa)
└── README.md           # Este documento
```

---

## ✅ Requisitos

- Python 3.10 o superior.
- Pip instalado.

Dependencias Python:

- `flask`

El resto de módulos utilizados pertenecen a la librería estándar.

---

## 💻 Instalación y ejecución

1. Clonar el repositorio:

   ```bash
   git clone https://github.com/davidgarciiapoli/metro-cdmx-ia
   cd metro-cdmx-ia
   ```

2. (Recomendado) Crear y activar un entorno virtual:

   ```bash
   python -m venv .venv

   # En Windows
   .\.venv\Scriptsctivate

   # En Linux/macOS
   # source .venv/bin/activate
   ```

3. Instalar dependencias:

   ```bash
   pip install flask
   ```

4. Ejecutar la aplicación:

   ```bash
   python cdmx.py
   ```

5. Abrir el navegador en:

   ```text
   http://127.0.0.1:5000/
   ```

6. Uso desde la interfaz:

   - Seleccionar **origen** y **destino**.
   - Elegir **fecha** y **hora** de salida.
   - Pulsar **“Buscar viaje”**.
   - Consultar:
     - Detalle de la ruta (estaciones, líneas, transbordos).
     - Duración total y hora de llegada.
     - Mapa interactivo con el recorrido.

---

## 🔎 Ejemplo de uso

1. Origen: `Tacubaya`  
2. Destino: `Centro Médico`  
3. Fecha: día laborable.  
4. Hora: 08:30.

La aplicación devuelve:

- Ruta óptima (posibles transbordos en estaciones comunes).
- Tiempo total aproximado y hora de llegada.
- Lista detallada de paradas.
- Mapa con la polilínea del recorrido.


---

## 🚧 Posibles mejoras futuras

- Permitir filtros de ruta:
  - “Evitar transbordos”.
  - “Priorizar accesibilidad” (penalizando estaciones sin ascensor).
- Soporte para más líneas y estaciones del metro.
- Soporte multiidioma (ES/EN).
- Panel de diagnóstico para mostrar:
  - Nodos explorados.
  - Costes `g(n)` y `h(n)` más relevantes.
- Despliegue en un servidor público (Railway, Render, etc.) para acceso sin entorno local.

---

## 👥 Autores

Proyecto desarrollado como parte de la práctica de **Inteligencia Artificial (GCDIA)**.

- David García Ropero – Coordinación general, integración y revisión.
- Kleart Laci Dreshaj – Algoritmo A* y funciones de coste.
- Marta Elena Fernández González – Modelo de datos y fichero CSV.
- Laura Silva Chirinos – Interfaz web (HTML/CSS, templates).
- Nora Ez Zahi – Mapa (Leaflet), pruebas y documentación.

---

## 📄 Licencia

Este proyecto se ha desarrollado con fines académicos.  
Se distribuye bajo la licencia **MIT** (o la que decidas configurar en GitHub).
