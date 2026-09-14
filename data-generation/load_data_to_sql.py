"""
Crea las tablas en Azure SQL y carga los archivos de output/.

    python load_data_to_sql.py

Antes hay que:
  - correr run_all.py
  - copiar db_config.example.yaml como db_config.yaml y llenarlo
  - tener instalado el ODBC Driver 18 for SQL Server
  - habilitar tu IP en el firewall del servidor en Azure
"""
import os
import re
import sys
import math
import yaml
import pandas as pd
import pyodbc

# el DDL vive en el .sql, no duplicado aca, para que no se desincronicen
RUTA_DDL = "../sql/01_modelo_relacional.sql"

# el orden importa: primero las dimensiones, si no las FK rechazan los hechos
TABLAS = [
    ("TB_CLIENTES_CORE",   "tb_clientes_core.csv",    "csv"),
    ("TB_PRODUCTOS_CAT",   "tb_productos_cat.json",   "json"),
    ("TB_SUCURSALES_RED",  "tb_sucursales_red.json",  "json"),
    ("TB_OBLIGACIONES",    "tb_obligaciones.csv",     "csv"),
    ("TB_MOV_FINANCIEROS", "tb_mov_financieros.csv",  "csv"),
    ("TB_COMISIONES_LOG",  "tb_comisiones_log.csv",   "csv"),
]

LOTE = 20000


def cargar_db_config(path="db_config.yaml"):
    if not os.path.exists(path):
        print(f"No se encontro {path}.")
        print("Copia db_config.example.yaml como db_config.yaml y completa los datos.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def conectar(cfg):
    cadena = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={cfg['server']},{cfg.get('port', 1433)};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['user']};"
        f"PWD={cfg['password']};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    print(f"Conectando a {cfg['server']}...")
    try:
        conn = pyodbc.connect(cadena)
    except pyodbc.Error as e:
        print(f"\nNo se pudo conectar: {e}")
        print("Revisa el firewall de Azure, el driver ODBC 18 y las credenciales.")
        sys.exit(1)
    print("Conectado.\n")
    return conn


def crear_tablas(conn):
    with open(RUTA_DDL, "r", encoding="utf-8") as f:
        script = f.read()

    # pyodbc no entiende GO, es un separador de SSMS, hay que partir el script
    lotes = [b.strip() for b in re.split(r"(?im)^\s*GO\s*$", script) if b.strip()]

    cursor = conn.cursor()
    for lote in lotes:
        cursor.execute(lote)
    conn.commit()
    cursor.close()
    print("Tablas creadas.")


def limpiar(v):
    # los NaN de pandas tienen que llegar como None para que SQL los tome como NULL
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if pd.isna(v):
        return None
    # pandas devuelve numpy.int64 y numpy.float64, que pyodbc no entiende.
    # .item() los convierte al tipo nativo de Python.
    if hasattr(v, "item"):
        return v.item()
    return v


def cargar_tabla(conn, tabla, archivo, formato, out_dir):
    ruta = f"{out_dir}/{archivo}"
    # num_doc es texto aunque parezca numero: hay documentos que empiezan
    # en cero y si pandas lo lee como numero se los borra
    df = pd.read_json(ruta) if formato == "json" else pd.read_csv(ruta, dtype={"num_doc": str})

    # los enteros con nulos llegan del CSV como float (100000.0),
    # se pasan a entero anulable para no insertar el decimal
    for col in df.columns:
        if df[col].dtype == "float64" and df[col].dropna().mod(1).eq(0).all():
            df[col] = df[col].astype("Int64")

    columnas = ", ".join(df.columns)
    marcadores = ", ".join("?" * len(df.columns))
    insert = f"INSERT INTO dbo.{tabla} ({columnas}) VALUES ({marcadores})"

    filas = [tuple(limpiar(v) for v in fila) for fila in df.itertuples(index=False, name=None)]

    cursor = conn.cursor()
    cursor.fast_executemany = True   # sin esto cargar 500 mil filas es eterno

    for i in range(0, len(filas), LOTE):
        cursor.executemany(insert, filas[i:i + LOTE])
        conn.commit()
        print(f"  {min(i + LOTE, len(filas)):,} / {len(filas):,}", end="\r")

    cursor.close()
    print(f"  {tabla:<20} {len(filas):>8,} filas cargadas       ")


def verificar(conn):
    print("\nConteo final por tabla:")
    cursor = conn.cursor()
    for tabla, _, _ in TABLAS:
        cursor.execute(f"SELECT COUNT(*) FROM dbo.{tabla}")
        print(f"  {tabla:<20} {cursor.fetchone()[0]:>8,}")

    print("\nAnomalias que quedaron en el origen:")
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT id_mov FROM dbo.TB_MOV_FINANCIEROS GROUP BY id_mov HAVING COUNT(*) > 1
        ) d
    """)
    print(f"  duplicados       {cursor.fetchone()[0]:>8,}")
    cursor.execute("""
        SELECT COUNT(*) FROM dbo.TB_MOV_FINANCIEROS
        WHERE fec_mov < '2015-01-01' OR fec_mov > '2027-12-31'
    """)
    print(f"  fechas malas     {cursor.fetchone()[0]:>8,}")
    cursor.execute("""
        SELECT COUNT(*) FROM dbo.TB_MOV_FINANCIEROS m
        WHERE NOT EXISTS (SELECT 1 FROM dbo.TB_CLIENTES_CORE c WHERE c.id_cli = m.id_cli)
    """)
    print(f"  id_cli huerfanos {cursor.fetchone()[0]:>8,}")
    cursor.execute("SELECT COUNT(*) FROM dbo.TB_MOV_FINANCIEROS WHERE vr_mov <= 0")
    print(f"  montos invalidos {cursor.fetchone()[0]:>8,}")
    cursor.close()


if __name__ == "__main__":
    with open("config.yaml", "r", encoding="utf-8") as f:
        out_dir = yaml.safe_load(f)["salida"]["directorio"]

    conn = conectar(cargar_db_config())

    crear_tablas(conn)

    print("\nCargando datos...")
    for tabla, archivo, formato in TABLAS:
        cargar_tabla(conn, tabla, archivo, formato, out_dir)

    verificar(conn)
    conn.close()
    print("\nCarga completa.")
