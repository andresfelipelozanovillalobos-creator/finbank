"""
Utilidades compartidas por todos los generadores.

Centraliza aqui la carga de config, el manejo de rutas de salida y los
nombres de archivo, para que ningun generador tenga rutas hardcodeadas.
"""
import os
import random
from datetime import date

import numpy as np
import pandas as pd
import yaml

# Carpeta donde vive este archivo. Permite ejecutar los scripts desde
# cualquier directorio sin que se rompan las rutas relativas.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Nombre base de cada tabla (sin extension). La extension la decide
# config.salida.formatos_por_tabla, no el codigo.
NOMBRES_TABLA = {
    "clientes":     "tb_clientes_core",
    "productos":    "tb_productos_cat",
    "sucursales":   "tb_sucursales_red",
    "obligaciones": "tb_obligaciones",
    "movimientos":  "tb_mov_financieros",
    "comisiones":   "tb_comisiones_log",
}

FORMATOS_SOPORTADOS = ("csv", "json", "parquet")

# Coordenadas aproximadas del centro de cada ciudad, para geolocalizar
# sucursales con jitter alrededor del punto.
COORDENADAS_CIUDAD = {
    "Bogota":           (4.7110, -74.0721),
    "Medellin":         (6.2442, -75.5812),
    "Cali":             (3.4516, -76.5320),
    "Barranquilla":     (10.9639, -74.7964),
    "Ciudad de Mexico": (19.4326, -99.1332),
    "Guadalajara":      (20.6597, -103.3496),
    "Lima":             (-12.0464, -77.0428),
    "Santiago":         (-33.4489, -70.6693),
    "Buenos Aires":     (-34.6037, -58.3816),
}


def cargar_config(path: str = None) -> dict:
    """Lee config.yaml desde la carpeta del proyecto."""
    path = path or os.path.join(BASE_DIR, "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dir_salida(config: dict) -> str:
    """Devuelve (y crea si hace falta) la carpeta de salida."""
    ruta = os.path.join(BASE_DIR, config["salida"]["directorio"])
    os.makedirs(ruta, exist_ok=True)
    return ruta


def formato(config: dict, tabla: str) -> str:
    """Formato de salida configurado para una tabla."""
    fmt = config["salida"]["formatos_por_tabla"].get(tabla, "csv").lower()
    if fmt not in FORMATOS_SOPORTADOS:
        raise ValueError(
            f"Formato '{fmt}' no soportado para la tabla '{tabla}'. "
            f"Usa uno de {FORMATOS_SOPORTADOS}."
        )
    return fmt


def ruta(config: dict, tabla: str) -> str:
    """Ruta absoluta del archivo de una tabla, con la extension del formato."""
    return os.path.join(
        dir_salida(config), f"{NOMBRES_TABLA[tabla]}.{formato(config, tabla)}"
    )


def guardar(df: pd.DataFrame, config: dict, tabla: str) -> str:
    """
    Escribe el DataFrame en el formato configurado para esa tabla.

    Tener esto centralizado es lo que permite cumplir el requisito de
    ingesta heterogenea cambiando una linea del YAML, sin tocar codigo.
    """
    fmt = formato(config, tabla)
    destino = ruta(config, tabla)

    if fmt == "csv":
        df.to_csv(destino, index=False, encoding="utf-8")
    elif fmt == "json":
        df.to_json(destino, orient="records", indent=2, force_ascii=False)
    else:  # parquet
        df.to_parquet(destino, index=False)

    return destino


def leer(config: dict, tabla: str) -> pd.DataFrame:
    """Lee una tabla ya generada, sea cual sea su formato."""
    fmt = formato(config, tabla)
    destino = ruta(config, tabla)

    if not os.path.exists(destino):
        raise FileNotFoundError(
            f"No existe {os.path.basename(destino)}. "
            f"Ejecuta primero el generador de '{tabla}' (o run_all.py)."
        )

    if fmt == "csv":
        return pd.read_csv(destino)
    if fmt == "json":
        return pd.read_json(destino)
    return pd.read_parquet(destino)


def fijar_semilla(config: dict, offset: int = 0) -> np.random.Generator:
    """
    Fija las semillas de random y numpy y devuelve un Generator moderno.

    El offset da a cada generador su propio flujo de aleatoriedad: asi,
    regenerar solo movimientos no altera los clientes ya generados.
    """
    semilla = config["seed"] + offset
    random.seed(semilla)
    np.random.seed(semilla)
    return np.random.default_rng(semilla)


def rango_fechas(config: dict):
    """Devuelve (fecha_inicio, fecha_fin, dias_totales) del periodo."""
    ini = date.fromisoformat(config["periodo"]["fecha_inicio"])
    fin = date.fromisoformat(config["periodo"]["fecha_fin"])
    if fin <= ini:
        raise ValueError("periodo.fecha_fin debe ser posterior a fecha_inicio")
    return ini, fin, (fin - ini).days


def pool_ciudades(config: dict):
    """
    Construye la lista de (ciudad, pais) y su vector de pesos normalizado.

    El pais principal concentra `peso_principal` y el resto se reparte
    en partes iguales entre los demas paises; dentro de cada pais, el
    peso se divide uniformemente entre sus ciudades.
    """
    principal = config["pesos_pais"]["principal"]
    peso_principal = config["pesos_pais"]["peso_principal"]
    otros = [p for p in config["paises"] if p["nombre"] != principal]
    peso_otro = (1 - peso_principal) / len(otros) if otros else 0

    ciudades, pesos = [], []
    for pais in config["paises"]:
        peso_pais = peso_principal if pais["nombre"] == principal else peso_otro
        for ciudad in pais["ciudades"]:
            ciudades.append((ciudad, pais["nombre"]))
            pesos.append(peso_pais / len(pais["ciudades"]))

    pesos = np.array(pesos, dtype=float)
    return ciudades, pesos / pesos.sum()


def inyectar_nulos(df: pd.DataFrame, columnas, pct: float, semilla: int) -> pd.DataFrame:
    """Pone a None un `pct` de las filas en cada columna indicada."""
    if pct <= 0:
        return df
    for i, col in enumerate(columnas):
        idx = df.sample(frac=pct, random_state=semilla + i).index
        df.loc[idx, col] = None
    return df


def resumen(df: pd.DataFrame, nombre: str, destino: str) -> None:
    """Imprime un resumen estandar tras generar una tabla."""
    print(f"\n{nombre}: {len(df):,} registros -> {os.path.basename(destino)}")
    print(df.head(3).to_string())
    nulos = df.isnull().sum()
    nulos = nulos[nulos > 0]
    if not nulos.empty:
        print("\n  Nulos por columna:")
        for col, n in nulos.items():
            print(f"    {col:<18} {n:>7,}  ({n / len(df):.1%})")
