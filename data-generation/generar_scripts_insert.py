"""
Convierte los archivos de output/ en scripts .sql que se ejecutan en SSMS.

    python generar_scripts_insert.py

Genera en ../sql/inserts/:
    00_crear_tablas.sql   el DDL (copia de 01_modelo_relacional.sql)
    01..06_<tabla>.sql    un script de INSERT por tabla

Se ejecutan en orden. El orden importa porque las tablas de hechos tienen
FK hacia clientes y productos.

Por que INSERT y no BULK INSERT: Azure SQL corre en un datacenter de
Microsoft y no puede leer archivos de tu disco. Un INSERT lleva los datos
escritos dentro del propio script, por eso si funciona.
"""
import os
import shutil
import pandas as pd
import yaml

SALIDA = "../sql/inserts"
DDL_ORIGEN = "../sql/01_modelo_relacional.sql"

# SQL Server acepta maximo 1000 filas por cada clausula VALUES
FILAS_POR_INSERT = 1000

# Si un .sql pasa de este tamano, SSMS se congela al abrirlo y toca
# partirlo en varios archivos.
MB_MAXIMO = 15

TABLAS = [
    ("01", "TB_CLIENTES_CORE",   "tb_clientes_core.csv",   "csv"),
    ("02", "TB_PRODUCTOS_CAT",   "tb_productos_cat.json",  "json"),
    ("03", "TB_SUCURSALES_RED",  "tb_sucursales_red.json", "json"),
    ("04", "TB_OBLIGACIONES",    "tb_obligaciones.csv",    "csv"),
    ("05", "TB_MOV_FINANCIEROS", "tb_mov_financieros.csv", "csv"),
    ("06", "TB_COMISIONES_LOG",  "tb_comisiones_log.csv",  "csv"),
]

# num_doc son digitos pero es texto: hay documentos que empiezan en cero y
# si pandas lo lee como numero se los borra.
COMO_TEXTO = {"num_doc": str}


def a_literal(valor):
    """Convierte un valor de pandas al literal que entiende T-SQL."""
    if valor is None or pd.isna(valor):
        return "null"
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (int, float)):
        return str(valor)
    # N delante para que respete los acentos, y las comillas simples
    # se escapan duplicandolas
    return "n'" + str(valor).replace("'", "''") + "'"


def leer(ruta, formato):
    if formato == "json":
        return pd.read_json(ruta)
    return pd.read_csv(ruta, dtype=COMO_TEXTO)


def bloques_insert(df, tabla):
    """Va entregando un INSERT completo por cada 1000 filas."""
    columnas = ", ".join(df.columns)
    acumulado = []

    for fila in df.itertuples(index=False, name=None):
        acumulado.append("(" + ", ".join(a_literal(v) for v in fila) + ")")

        if len(acumulado) == FILAS_POR_INSERT:
            yield f"insert into dbo.{tabla.lower()} ({columnas}) values\n" + \
                  ",\n".join(acumulado) + ";\ngo\n"
            acumulado = []

    if acumulado:
        yield f"insert into dbo.{tabla.lower()} ({columnas}) values\n" + \
              ",\n".join(acumulado) + ";\ngo\n"


def escribir(tabla, orden, df):
    """
    Escribe el script de una tabla. Si se pasa de MB_MAXIMO lo corta en
    varias partes, para que SSMS pueda abrirlas.
    """
    limite_bytes = MB_MAXIMO * 1024 * 1024
    archivos = []
    parte = 1
    buffer = []
    tamano = 0

    def guardar(buffer, parte, ultima):
        nombre = f"{orden}_{tabla.lower()}.sql" if parte == 1 and ultima \
                 else f"{orden}_{tabla.lower()}_parte{parte:02d}.sql"
        ruta = f"{SALIDA}/{nombre}"
        # utf-8-sig (con BOM) para que SSMS no dane los acentos
        with open(ruta, "w", encoding="utf-8-sig") as f:
            f.write("set nocount on;\ngo\n\n")
            f.write("\n".join(buffer))
            if ultima:
                f.write(f"\nselect count(*) as filas_en_{tabla.lower()} "
                        f"from dbo.{tabla.lower()};\ngo\n")
        return ruta

    todos = list(bloques_insert(df, tabla))

    for i, bloque in enumerate(todos):
        buffer.append(bloque)
        tamano += len(bloque.encode("utf-8"))
        es_el_ultimo = (i == len(todos) - 1)

        if tamano >= limite_bytes or es_el_ultimo:
            archivos.append(guardar(buffer, parte, es_el_ultimo))
            buffer, tamano = [], 0
            parte += 1

    return archivos


if __name__ == "__main__":
    with open("config.yaml", "r", encoding="utf-8") as f:
        out_dir = yaml.safe_load(f)["salida"]["directorio"]

    os.makedirs(SALIDA, exist_ok=True)

    # el DDL va de primero, con el nombre 00 para que quede claro el orden
    shutil.copy(DDL_ORIGEN, f"{SALIDA}/00_crear_tablas.sql")
    print(f"{'00_crear_tablas.sql':<45} (DDL de las 6 tablas)")

    total_filas = 0
    for orden, tabla, archivo, formato in TABLAS:
        df = leer(f"{out_dir}/{archivo}", formato)
        archivos = escribir(tabla, orden, df)
        total_filas += len(df)

        for ruta in archivos:
            mb = os.path.getsize(ruta) / 1024 / 1024
            etiqueta = os.path.basename(ruta)
            print(f"{etiqueta:<45} {len(df) if len(archivos) == 1 else '':>8} "
                  f"{mb:>7.1f} MB")

    print(f"\n{total_filas:,} filas en total, scripts en {os.path.abspath(SALIDA)}")
    print("Ejecutalos en SSMS en orden: 00, luego 01 hasta 06.")
    print("Los que digan parte01, parte02... van uno tras otro.")
