from flask import Flask, request, render_template, redirect, url_for
import csv
from datetime import datetime, timedelta, time
import heapq
import math
import os
from typing import Dict, Any, List, Tuple

app = Flask(__name__)


# -----------------------------
# Clase Estacion y Carga de Grafo
# -----------------------------
class Estacion:
    """
    Representa una estación de metro/tren, incluyendo la información
    de accesibilidad.
    """

    def __init__(self, data: Dict[str, Any]):
        # Conversión de tipos segura
        self.num = int(data.get('nº', 0))
        self.nombre = data.get('nombre', 'Desconocida')
        self.lat = float(data.get('lat', 0.0))
        self.lng = float(data.get('lng', 0.0))
        self.linea = int(data.get('linea', 0))
        self.IDs = int(data.get('IDs', 0))

        # --- NUEVOS ATRIBUTOS DE ACCESIBILIDAD ---
        # ATENCIÓN: Se asume que la columna es 'mecánica' con tilde.
        self.escalera: int = int(data.get('escalera', 0))
        self.mecanica: int = int(data.get('mecánica', 0)) # <--- Debe ser 'mecánica' con tilde
        self.ascensor: int = int(data.get('ascensor', 0))

        # Horarios y frecuencias
        self.dir_izq = self._parse_first_train_time(data.get('dir_izq', '00:00'))
        self.dir_der = self._parse_first_train_time(data.get('dir_der', '00:00'))
        self.frec = int(data.get('frec', 10))
        self.dir_izq_s = self._parse_first_train_time(data.get('dir_izq_s', '00:00'))
        self.dir_der_s = self._parse_first_train_time(data.get('dir_der_s', '00:00'))
        self.frec_finde = int(data.get('frec_finde', 15))
        self.dir_izq_d = self._parse_first_train_time(data.get('dir_izq_d', '00:00'))
        self.dir_der_d = self._parse_first_train_time(data.get('dir_der_d', '00:00'))
        self.tiempo_sig = int(data.get('tiempo_sig', 5))
        self.tiempo_ant = int(data.get('tiempo_ant', 5))

        # Vecinos se almacenarán como: (nombre_vecino, linea_vecino, tiempo_a_vecino, es_transbordo)
        self.vecinos: List[Tuple[str, int, int, bool]] = []

    @property
    def accesibilidad(self):
        """
        Retorna los datos de accesibilidad en formato de diccionario
        para que Jinja pueda acceder a ellos fácilmente (stop.accesibilidad.escalera).
        """
        return {
            'escalera': self.escalera,
            'mecanica': self.mecanica,
            'ascensor': self.ascensor
        }

    def _parse_first_train_time(self, hora_str: str) -> time:
        # Asegura que la hora (ej: '5:30') se formatee con cero inicial ('05:30') para datetime
        try:
            parts = hora_str.split(':')
            if len(parts) == 2:
                return time(int(parts[0]), int(parts[1]))
            else:
                return time(0, 0)
        except (ValueError, AttributeError):
            return time(0, 0)

    # Nota: Se elimina obtener_accesibilidad() ya que es redundante con @property accesibilidad
    # y solo crea confusión en el código.

def cargar_estaciones():
    # estaciones_por_nombre: {'Pino Suárez': [Estacion_L1, Estacion_L2]}
    estaciones_por_nombre: Dict[str, List[Estacion]] = {}
    # estaciones_por_nombre_linea: {('Pino Suárez', 1): Estacion_L1}
    estaciones_por_nombre_linea: Dict[Tuple[str, int], Estacion] = {}

    csv_path = 'CDMX.csv'
    try:
        # Nota: En un entorno real, usar os.path.join para asegurar la ruta.
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                est = Estacion(row)
                estaciones_por_nombre_linea[(est.nombre, est.linea)] = est
                if est.nombre not in estaciones_por_nombre:
                    estaciones_por_nombre[est.nombre] = []
                estaciones_por_nombre[est.nombre].append(est)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{csv_path}'. Asegúrate de que esté en el mismo directorio.")
        return {}, {}
    except Exception as e:
        print(f"Error al leer el archivo CSV: {e}")
        return {}, {}

    # 1. Construir vecinos de línea (siguiente/anterior)
    for est in estaciones_por_nombre_linea.values():

        # Vecino siguiente (mayor ID)
        for e in estaciones_por_nombre_linea.values():
            if e.linea == est.linea and e.IDs == est.IDs + 1:
                # (nombre_vecino, linea_vecino, tiempo_a_vecino, es_transbordo)
                est.vecinos.append((e.nombre, e.linea, est.tiempo_sig, False))
                break

                # Vecino anterior (menor ID)
        for e in estaciones_por_nombre_linea.values():
            if e.linea == est.linea and e.IDs == est.IDs - 1:
                est.vecinos.append((e.nombre, e.linea, est.tiempo_ant, False))
                break

                # 2. Construir transbordos (mismo nombre, diferente línea)
    TIEMPO_TRANSBORDO = 5  # 5 minutos fijos para transbordo
    for nombre, estaciones_mismo_nombre in estaciones_por_nombre.items():
        if len(estaciones_mismo_nombre) > 1:  # Es una estación de transbordo
            for i in range(len(estaciones_mismo_nombre)):
                for j in range(len(estaciones_mismo_nombre)):
                    if i != j:
                        est_origen = estaciones_mismo_nombre[i]
                        est_destino = estaciones_mismo_nombre[j]
                        # El tiempo de transbordo es el coste del arco entre sub-estaciones
                        est_origen.vecinos.append((est_destino.nombre, est_destino.linea, TIEMPO_TRANSBORDO, True))

    return estaciones_por_nombre, estaciones_por_nombre_linea


estaciones_por_nombre, estaciones_por_nombre_linea = cargar_estaciones()


# -----------------------------
# Funciones de Tiempo y Heurística
# -----------------------------
def parse_hora(t: time) -> timedelta:
    # Convierte un objeto time a timedelta para operaciones
    if isinstance(t, time):
        return timedelta(hours=t.hour, minutes=t.minute)
    return t


def siguiente_salida(est: Estacion, vecino_name: str, tiempo_actual: timedelta, fecha_actual: datetime,
                     es_transbordo: bool) -> timedelta:
    # Si es transbordo, no hay tren, el 'viaje' empieza de inmediato
    if es_transbordo:
        return tiempo_actual

    dia_semana = fecha_actual.weekday()  # 0=Lunes ... 6=Domingo

    if dia_semana < 5:  # Lunes a Viernes
        frecuencia = est.frec
        primer_tren_izq = parse_hora(est.dir_izq)
        primer_tren_der = parse_hora(est.dir_der)
    elif dia_semana == 5:  # Sábado
        frecuencia = est.frec_finde
        primer_tren_izq = parse_hora(est.dir_izq_s)
        primer_tren_der = parse_hora(est.dir_der_s)
    else:  # Domingo
        frecuencia = est.frec_finde
        primer_tren_izq = parse_hora(est.dir_izq_d)
        primer_tren_der = parse_hora(est.dir_der_d)

    # Determinar la dirección del tren basándose en el IDs del vecino
    vecino_est_data = next(((n, l, d, t) for n, l, d, t in est.vecinos if n == vecino_name and not t),
                           None)  # Buscamos el vecino en línea

    inicio = None
    if vecino_est_data:
        vecino_key = (vecino_est_data[0], vecino_est_data[1])
        vecino_sub_est = estaciones_por_nombre_linea.get(vecino_key)
        if vecino_sub_est and vecino_sub_est.IDs > est.IDs:
            inicio = primer_tren_der
        elif vecino_sub_est and vecino_sub_est.IDs < est.IDs:
            inicio = primer_tren_izq

    if inicio is None:
        # No se pudo determinar la dirección o es un vecino de transbordo (ya manejado)
        return tiempo_actual

        # Parada del servicio a medianoche (00:00).
    tiempo_limite = timedelta(hours=24)

    # Si la hora actual es después del límite de servicio, no hay más trenes hoy.
    if tiempo_actual >= tiempo_limite:
        return tiempo_limite

        # Si la hora actual es antes del primer tren
    if tiempo_actual < inicio:
        return inicio

        # Calcular próximo tren después de la hora actual
    diff_min = (tiempo_actual - inicio).total_seconds() // 60

    if frecuencia > 0:
        ciclos = math.ceil(diff_min / frecuencia)
    else:
        ciclos = 0

    prox_tren = inicio + timedelta(minutes=ciclos * frecuencia)

    # Si el próximo tren excede la medianoche, se considera el servicio terminado.
    if prox_tren >= tiempo_limite:
        return tiempo_limite

    return prox_tren


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def heuristica(est1: Estacion, est2: Estacion) -> float:
    # La heurística usa la distancia geodésica convertida a tiempo
    VELOCIDAD_MAX_KMH = 50
    distancia_km = haversine(est1.lat, est1.lng, est2.lat, est2.lng)
    tiempo_h = distancia_km / VELOCIDAD_MAX_KMH
    return tiempo_h * 60  # Retorna el tiempo en minutos


def astar(origen: str, destino: str, hora_actual: timedelta, fecha_actual: datetime) -> Tuple[
    List[Tuple[str, int]] | None, timedelta | None]:
    if origen not in estaciones_por_nombre or destino not in estaciones_por_nombre:
        return None, None

    # El path almacenará (station_name, line_id)
    open_set: List[Tuple[float, str, int, List[Tuple[str, int]], timedelta]] = []

    # Usamos la primera sub-estación del destino para calcular la heurística inicial
    destino_est_ref = estaciones_por_nombre[destino][0]

    for est_origen_sub in estaciones_por_nombre[origen]:
        h_score = heuristica(est_origen_sub, destino_est_ref)
        f_score_min = h_score

        path_start = [(est_origen_sub.nombre, est_origen_sub.linea)]

        # key = (f_score, name, line, path, arrival_timedelta)
        heapq.heappush(open_set, (f_score_min, est_origen_sub.nombre, est_origen_sub.linea, path_start, hora_actual))

    # visited guarda el tiempo_llegada_timedelta más corto encontrado hasta ahora para una (name, line)
    visited: Dict[Tuple[str, int], timedelta] = {}

    while open_set:
        fscore, current_name, current_linea, path, tiempo_llegada_timedelta = heapq.heappop(open_set)

        current_key = (current_name, current_linea)
        est_actual = estaciones_por_nombre_linea.get(current_key)

        if not est_actual: continue

        if current_name == destino:
            return path, tiempo_llegada_timedelta

        if current_key in visited and visited[current_key] <= tiempo_llegada_timedelta:
            continue

        visited[current_key] = tiempo_llegada_timedelta

        # Explorar vecinos
        for vecino_name, vecino_linea, duracion_min, es_transbordo in est_actual.vecinos:
            vecino_key = (vecino_name, vecino_linea)
            vecino_est = estaciones_por_nombre_linea.get(vecino_key)
            if not vecino_est: continue

            # 1. Calcular el tiempo de espera
            tiempo_salida_tren = siguiente_salida(est_actual, vecino_name, tiempo_llegada_timedelta, fecha_actual,
                                                  es_transbordo)

            if tiempo_salida_tren >= timedelta(hours=24): continue

            tiempo_espera_min = (tiempo_salida_tren - tiempo_llegada_timedelta).total_seconds() / 60
            if tiempo_espera_min < 0: tiempo_espera_min = 0

            # 2. Calcular el tiempo total de llegada al vecino
            nuevo_tiempo_timedelta = tiempo_llegada_timedelta + timedelta(minutes=tiempo_espera_min + duracion_min)
            nuevo_g_score_min = nuevo_tiempo_timedelta.total_seconds() / 60

            # 3. Calcular el f_score
            h_score_vecino = heuristica(vecino_est, destino_est_ref)
            fscore_nuevo = nuevo_g_score_min + h_score_vecino

            # 4. Añadir a la cola de prioridad
            new_path = path + [(vecino_name, vecino_linea)]

            heapq.heappush(open_set, (fscore_nuevo, vecino_name, vecino_linea, new_path, nuevo_tiempo_timedelta))

    return None, None


# -----------------------------
# Rutas de Flask
# -----------------------------
@app.route('/')
def index():
    now = datetime.now()
    fecha_hoy = now.strftime('%Y-%m-%d')
    hora_actual = now.strftime('%H:%M')

    estaciones_unicas = sorted(list(estaciones_por_nombre.keys()))

    return render_template('index.html', estaciones=estaciones_unicas, fecha_hoy=fecha_hoy, hora_actual=hora_actual)


@app.route('/buscar', methods=['POST'])
def buscar():
    origen = request.form.get('origen')
    destino = request.form.get('destino')
    fecha_str = request.form.get('fecha')
    hora_str = request.form.get('hora')

    if not origen or not destino or not fecha_str or not hora_str:
        return "<h2>Error: Faltan datos en el formulario.</h2>", 400

    try:
        fecha_actual = datetime.strptime(fecha_str, "%Y-%m-%d")
        hora_str_padded = hora_str.zfill(5)
        hora_inicio_time = datetime.strptime(hora_str_padded, "%H:%M").time()
        hora_inicio_timedelta = timedelta(hours=hora_inicio_time.hour, minutes=hora_inicio_time.minute)

    except ValueError:
        return "<h2>Error en el formato de fecha u hora.</h2>", 400

    # ruta_con_lineas contiene una lista de (nombre, linea)
    ruta_con_lineas, tiempo_final_timedelta = astar(origen, destino, hora_inicio_timedelta, fecha_actual)

    if ruta_con_lineas and tiempo_final_timedelta is not None:

        llegada_datetime = datetime.combine(fecha_actual, datetime.min.time()) + tiempo_final_timedelta
        llegada = llegada_datetime.strftime('%H:%M')

        tiempo_total_min = int(tiempo_final_timedelta.total_seconds() // 60) - int(
            hora_inicio_timedelta.total_seconds() // 60)

        # --- LÓGICA PARA FORMATEAR LA RUTA DE DISPLAY ---
        ruta_display = []
        ruta_coords = []

        last_name = None
        last_line = None

        for i, (name, line) in enumerate(ruta_con_lineas):
            stop_type = 'intermediate'

            is_start = i == 0
            is_end = name == destino and i == len(ruta_con_lineas) - 1
            is_new_name = i > 0 and name != ruta_con_lineas[i - 1][0]
            is_transfer_entry = i > 0 and name == ruta_con_lineas[i - 1][0] and line != ruta_con_lineas[i - 1][1]
            current_sub_est = estaciones_por_nombre_linea.get((name, line))
            accesibilidad_data = current_sub_est.accesibilidad if current_sub_est else None

            # Condición de agregado:
            # 1. Es el inicio.
            # 2. El nombre de la estación cambia (es una nueva estación en la línea).
            # 3. Es un punto de transbordo (nombre igual, línea diferente).
            if is_start or is_new_name or is_transfer_entry:
                # *** CÓDIGO ACTUALIZADO: OBTENER DATOS DE ACCESIBILIDAD ***

                # Se utiliza el atributo 'accesibilidad' que es el @property

                # *********************************************************

                if is_start:
                    stop_type = 'start'
                elif is_end:
                    stop_type = 'end'
                elif is_transfer_entry:
                    stop_type = 'transfer'
                    # Si el elemento anterior es el mismo nombre pero diferente línea,
                    # marcamos el anterior como intermedio antes de la entrada al transbordo.
                    if ruta_display and ruta_display[-1]['name'] == name:
                        # Se trata de la misma estación, solo cambia la línea. Esto ya lo maneja 'transfer'
                        pass


                # Si el último elemento agregado tiene el mismo nombre, solo agregamos si la línea cambió (transfer)
                if ruta_display and ruta_display[-1]['name'] == name:
                    if ruta_display[-1]['line'] != line:
                        stop_type = 'transfer'
                        if is_end: stop_type = 'end'

                        ruta_display.append({
                            'name': name,
                            'line': line,
                            'type': stop_type,
                            'accesibilidad': accesibilidad_data  # AÑADIDO
                        })
                else:
                    # Es una nueva parada o el inicio.
                    ruta_display.append({
                        'name': name,
                        'line': line,
                        'type': stop_type,
                        'accesibilidad': accesibilidad_data  # AÑADIDO
                    })

        # Limpieza de tipo final: Asegurar que el destino y el origen estén marcados correctamente
        if ruta_display and ruta_display[-1]['name'] == destino:
            ruta_display[-1]['type'] = 'end'
        if ruta_display and ruta_display[0]['name'] == origen:
            ruta_display[0]['type'] = 'start'

        ruta_coords = []
        for stop in ruta_display:
            est = estaciones_por_nombre_linea.get((stop['name'], stop['line']))
            if est:
                ruta_coords.append({
                    'name': stop['name'],
                    'lat': est.lat,
                    'lng': est.lng
                })

        return render_template('results.html',
                               origen=origen,
                               destino=destino,
                               fecha_busqueda=fecha_str,
                               hora_busqueda=hora_str_padded,
                               ruta_display=ruta_display,
                               llegada=llegada,
                               tiempo_total=tiempo_total_min,
                               ruta_coords=ruta_coords)


    else:
        # No se encontró ruta
        return render_template('results.html',
                               origen=origen,
                               destino=destino,
                               fecha_busqueda=fecha_str,
                               hora_busqueda=hora_str_padded,
                               ruta_display=None,
                               llegada=None,
                               tiempo_total=None)


if __name__ == '__main__':
    # Nota: Asegúrate de que 'templates/index.html', 'templates/results.html' y 'CDMX.csv'
    # estén en la ubicación esperada.
    app.run(debug=True)