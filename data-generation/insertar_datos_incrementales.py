"""
Mete movimientos y comisiones con la fecha de hoy, para probar la carga
incremental. El historico llega hasta la fecha_fin del config, asi que
todo lo que inserte este script es nuevo para el pipeline.

Se puede correr varias veces, los ids llevan la hora y no chocan.

    python insertar_datos_incrementales.py
"""
import random
from datetime import datetime

import pyodbc
from load_data_to_sql import cargar_db_config, conectar

N_MOVIMIENTOS = 40
N_COMISIONES = 15

CANALES = ["App Movil", "Portal Web", "Cajero Automatico", "Corresponsal Bancario"]
TIPOS_MOV = ["pago_capital", "pago_interes", "transferencia", "retiro", "compra_tc", "desembolso"]
TIPOS_COMISION = ["Comision Retiro Cajero", "Comision Transferencia",
                  "Comision Manejo Cuenta", "Comision Administracion"]


def leer_llaves(conn):
    """Se leen de la base, no se hardcodean, asi nunca se insertan huerfanos."""
    cursor = conn.cursor()
    cursor.execute("SELECT id_cli FROM dbo.TB_CLIENTES_CORE")
    clientes = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT cod_prod FROM dbo.TB_PRODUCTOS_CAT WHERE estado_prod = 'Activo'")
    productos = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT ciudad_res FROM dbo.TB_CLIENTES_CORE WHERE ciudad_res IS NOT NULL")
    ciudades = [r[0] for r in cursor.fetchall()]
    cursor.close()
    return clientes, productos, ciudades


def insertar_movimientos(cursor, clientes, productos, ciudades, marca):
    hoy = datetime.now().date()
    filas = []
    for i in range(N_MOVIMIENTOS):
        cliente = random.choice(clientes)
        hora = f"{random.randint(6, 22):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
        filas.append((
            f"MOV-INC-{marca}-{i:03d}",
            cliente,
            random.choice(productos),
            f"CTA-{random.randint(10**9, 10**10 - 1)}",
            hoy,
            hora,
            round(random.lognormvariate(10.5, 1.1), 2),
            random.choice(TIPOS_MOV),
            random.choice(CANALES),
            random.choice(ciudades),
            "Aprobado",
            f"DEV-{random.randint(100000, 999999)}",
        ))

    cursor.fast_executemany = True
    cursor.executemany("""
        INSERT INTO dbo.TB_MOV_FINANCIEROS
            (id_mov, id_cli, cod_prod, num_cuenta, fec_mov, hra_mov, vr_mov,
             tip_mov, cod_canal, cod_ciudad, cod_estado_mov, id_dispositivo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, filas)
    print(f"  {len(filas)} movimientos insertados con fecha {hoy}")


def insertar_comisiones(cursor, clientes, productos, marca):
    hoy = datetime.now().date()
    filas = [(
        f"COM-INC-{marca}-{i:03d}",
        random.choice(clientes),
        random.choice(productos),
        hoy,
        round(random.uniform(2000, 40000), 2),
        random.choice(TIPOS_COMISION),
        "Cobrado",
    ) for i in range(N_COMISIONES)]

    cursor.fast_executemany = True
    cursor.executemany("""
        INSERT INTO dbo.TB_COMISIONES_LOG
            (id_comision, id_cli, cod_prod, fec_cobro, vr_comision, tip_comision, estado_cobro)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, filas)
    print(f"  {len(filas)} comisiones insertadas con fecha {hoy}")


if __name__ == "__main__":
    conn = conectar(cargar_db_config())
    clientes, productos, ciudades = leer_llaves(conn)

    if not clientes:
        print("La base esta vacia, corre primero load_data_to_sql.py")
        raise SystemExit(1)

    marca = datetime.now().strftime("%Y%m%d%H%M%S")
    cursor = conn.cursor()

    try:
        insertar_movimientos(cursor, clientes, productos, ciudades, marca)
        insertar_comisiones(cursor, clientes, productos, marca)
        conn.commit()
    except pyodbc.Error as e:
        conn.rollback()
        print(f"Error al insertar, se revirtio todo: {e}")
        raise SystemExit(1)

    cursor.execute("SELECT COUNT(*) FROM dbo.TB_MOV_FINANCIEROS WHERE fec_mov = ?",
                   datetime.now().date())
    print(f"\nTotal de movimientos de hoy en el origen: {cursor.fetchone()[0]:,}")

    cursor.close()
    conn.close()
    print("Datos nuevos disponibles para el pipeline incremental.")
