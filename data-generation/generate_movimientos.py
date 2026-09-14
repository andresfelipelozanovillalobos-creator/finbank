import random
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from generate_clientes import cargar_config

# Estacionalidad del sector: diciembre se dispara por prima y navidad,
# enero cae por la cuesta de enero, junio sube por la prima de mitad de ano.
FACTOR_MES = {1: 0.80, 2: 0.90, 3: 0.95, 4: 0.95, 5: 1.00, 6: 1.10,
              7: 1.00, 8: 0.95, 9: 0.95, 10: 1.00, 11: 1.15, 12: 1.40}

# lunes=0 ... domingo=6
FACTOR_DIA_SEMANA = {0: 1.10, 1: 1.05, 2: 1.00, 3: 1.00, 4: 1.15, 5: 0.70, 6: 0.45}

# dias de pago de nomina
FACTOR_QUINCENA = {1: 1.45, 14: 1.35, 15: 1.70, 16: 1.45, 29: 1.35, 30: 1.70, 31: 1.50}

TIPOS_MOV = ["pago_interes", "pago_capital", "desembolso", "compra_tc", "retiro", "transferencia"]
PESOS_TIPO = [0.20, 0.25, 0.10, 0.20, 0.15, 0.10]

CANALES = ["App Movil", "Portal Web", "Corresponsal Bancario", "Cajero Automatico"]
PESOS_CANAL = [0.45, 0.30, 0.15, 0.10]

ESTADOS = ["Aprobado", "Rechazado", "Pendiente"]
PESOS_ESTADO = [0.94, 0.04, 0.02]


def pesos_por_dia(fecha_inicio, dias):
    """Peso de cada dia del periodo: mes x dia de semana x quincena."""
    pesos = []
    for i in range(dias + 1):
        d = fecha_inicio + timedelta(days=i)
        pesos.append(FACTOR_MES[d.month]
                     * FACTOR_DIA_SEMANA[d.weekday()]
                     * FACTOR_QUINCENA.get(d.day, 1.0))
    pesos = np.array(pesos)
    return pesos / pesos.sum()


def horas_del_dia(n):
    """Horas concentradas en horario laboral, con pico al almuerzo y a la salida."""
    r = np.random.random(n)
    horas = np.where(r < 0.20, np.random.randint(11, 14, n),
             np.where(r < 0.45, np.random.randint(17, 20, n),
              np.where(r < 0.90, np.random.randint(8, 22, n),
                       np.random.randint(0, 24, n))))
    return horas


def generar_movimientos(config, df_clientes, df_productos):
    seed = config["seed"]
    random.seed(seed + 4)
    np.random.seed(seed + 4)

    n_total = config["volumenes"]["movimientos"]
    fecha_inicio = date.fromisoformat(config["periodo"]["fecha_inicio"])
    fecha_fin = date.fromisoformat(config["periodo"]["fecha_fin"])
    dias = (fecha_fin - fecha_inicio).days

    pct = config["anomalias"]
    n_fechas_malas = int(n_total * pct["pct_fechas_fuera_rango"])
    n_huerfanos = int(n_total * pct["pct_ids_huerfanos"])
    n_montos_malos = int(n_total * pct["pct_montos_invalidos"])
    n_duplicados = int(n_total * pct["pct_duplicados"])
    n_limpios = n_total - n_fechas_malas - n_huerfanos - n_montos_malos

    ids_clientes = df_clientes["id_cli"].tolist()
    ids_productos = df_productos[df_productos["estado_prod"] == "Activo"]["cod_prod"].tolist()
    ciudades = df_clientes["ciudad_res"].dropna().unique().tolist()

    # cada cliente tiene una cuenta fija, no una distinta por transaccion
    cuentas = {c: f"CTA-{random.randint(10**9, 10**10 - 1)}" for c in ids_clientes}

    # se sortea todo de una vez y despues se arma el dataframe,
    # asi no se llama a numpy 500 mil veces dentro del loop
    pesos = pesos_por_dia(fecha_inicio, dias)
    offsets = np.random.choice(dias + 1, size=n_limpios, p=pesos)
    horas = horas_del_dia(n_limpios)
    minutos = np.random.randint(0, 60, n_limpios)
    segundos = np.random.randint(0, 60, n_limpios)
    # log-normal: muchos movimientos pequenos y unos pocos muy grandes
    montos = np.round(np.random.lognormal(10.5, 1.1, n_limpios), -2)
    tipos = np.random.choice(TIPOS_MOV, size=n_limpios, p=PESOS_TIPO)
    canales = np.random.choice(CANALES, size=n_limpios, p=PESOS_CANAL)
    estados = np.random.choice(ESTADOS, size=n_limpios, p=PESOS_ESTADO)

    registros = []
    for i in range(n_limpios):
        id_cli = random.choice(ids_clientes)
        fec = fecha_inicio + timedelta(days=int(offsets[i]))
        registros.append({
            "id_mov": None,
            "id_cli": id_cli,
            "cod_prod": random.choice(ids_productos),
            "num_cuenta": cuentas[id_cli],
            "fec_mov": fec.isoformat(),
            "hra_mov": f"{horas[i]:02d}:{minutos[i]:02d}:{segundos[i]:02d}",
            "vr_mov": montos[i],
            "tip_mov": tipos[i],
            "cod_canal": canales[i],
            "cod_ciudad": random.choice(ciudades),
            "cod_estado_mov": estados[i],
            "id_dispositivo": f"DEV-{random.randint(100000, 999999)}",
        })

    # ANOMALIA 1: fechas imposibles para el periodo
    for _ in range(n_fechas_malas):
        id_cli = random.choice(ids_clientes)
        if random.random() < 0.5:
            fec = date(random.randint(2005, 2014), random.randint(1, 12), random.randint(1, 28))
        else:
            fec = date(2030, random.randint(1, 12), random.randint(1, 28))
        registros.append({
            "id_mov": None,
            "id_cli": id_cli,
            "cod_prod": random.choice(ids_productos),
            "num_cuenta": cuentas[id_cli],
            "fec_mov": fec.isoformat(),
            "hra_mov": f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00",
            "vr_mov": round(random.lognormvariate(10.5, 1.1), -2),
            "tip_mov": random.choice(TIPOS_MOV),
            "cod_canal": random.choice(CANALES),
            "cod_ciudad": random.choice(ciudades),
            "cod_estado_mov": "Aprobado",
            "id_dispositivo": f"DEV-{random.randint(100000, 999999)}",
        })

    # ANOMALIA 2: id_cli que no existe en la tabla de clientes
    max_id = max(ids_clientes)
    for _ in range(n_huerfanos):
        fec = fecha_inicio + timedelta(days=random.randint(0, dias))
        registros.append({
            "id_mov": None,
            "id_cli": max_id + random.randint(1, 99999),
            "cod_prod": random.choice(ids_productos),
            "num_cuenta": f"CTA-{random.randint(10**9, 10**10 - 1)}",
            "fec_mov": fec.isoformat(),
            "hra_mov": f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00",
            "vr_mov": round(random.lognormvariate(10.5, 1.1), -2),
            "tip_mov": random.choice(TIPOS_MOV),
            "cod_canal": random.choice(CANALES),
            "cod_ciudad": random.choice(ciudades),
            "cod_estado_mov": "Aprobado",
            "id_dispositivo": f"DEV-{random.randint(100000, 999999)}",
        })

    # ANOMALIA 3: montos en cero o negativos
    for _ in range(n_montos_malos):
        id_cli = random.choice(ids_clientes)
        fec = fecha_inicio + timedelta(days=random.randint(0, dias))
        registros.append({
            "id_mov": None,
            "id_cli": id_cli,
            "cod_prod": random.choice(ids_productos),
            "num_cuenta": cuentas[id_cli],
            "fec_mov": fec.isoformat(),
            "hra_mov": f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00",
            "vr_mov": random.choice([0.0, -round(random.uniform(1000, 50000), -2)]),
            "tip_mov": random.choice(TIPOS_MOV),
            "cod_canal": random.choice(CANALES),
            "cod_ciudad": random.choice(ciudades),
            "cod_estado_mov": "Aprobado",
            "id_dispositivo": f"DEV-{random.randint(100000, 999999)}",
        })

    # el id se asigna al final, cuando ya estan todas las filas
    for i, r in enumerate(registros):
        r["id_mov"] = f"MOV-{i+1:07d}"

    df = pd.DataFrame(registros)

    # ANOMALIA 4: duplicados exactos. Se duplica despues de poner el id
    # para que se repita la fila completa, id incluido.
    repetidas = df.sample(n=n_duplicados, random_state=seed)
    df = pd.concat([df, repetidas], ignore_index=True)

    # se mezcla para que las anomalias no queden todas al final del archivo
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    # no toda transaccion viene de un dispositivo, las de ventanilla no
    idx_nulos = df.sample(frac=config["calidad"]["pct_nulos"], random_state=seed + 4).index
    df.loc[idx_nulos, "id_dispositivo"] = None

    return df


if __name__ == "__main__":
    cfg = cargar_config()
    out_dir = cfg["salida"]["directorio"]

    df_clientes = pd.read_csv(f"{out_dir}/tb_clientes_core.csv")
    df_productos = pd.read_json(f"{out_dir}/tb_productos_cat.json")

    df = generar_movimientos(cfg, df_clientes, df_productos)
    df.to_csv(f"{out_dir}/tb_mov_financieros.csv", index=False, encoding="utf-8")

    print(f"Generados {len(df)} movimientos -> {out_dir}/tb_mov_financieros.csv")
    print(df.head(5).to_string())

    print("\nAnomalias sembradas:")
    fechas = pd.to_datetime(df["fec_mov"])
    print("  1. duplicados exactos:  ", df["id_mov"].duplicated().sum())
    print("  2. fechas fuera de rango:", ((fechas.dt.year < 2015) | (fechas.dt.year > 2027)).sum())
    print("  3. id_cli huerfanos:    ", (~df["id_cli"].isin(df_clientes["id_cli"])).sum())
    print("  4. montos invalidos:    ", (df["vr_mov"] <= 0).sum())

    print("\nMovimientos por mes (estacionalidad):")
    validas = fechas[(fechas.dt.year >= 2015) & (fechas.dt.year <= 2027)]
    print(validas.dt.to_period("M").value_counts().sort_index())

    print("\nDistribucion por franja horaria:")
    horas = pd.to_datetime(df["hra_mov"], format="%H:%M:%S").dt.hour
    franjas = pd.cut(horas, bins=[-1, 7, 10, 13, 16, 19, 23],
                     labels=["madrugada", "manana", "almuerzo", "tarde", "salida", "noche"])
    print(franjas.value_counts(normalize=True).round(3))

    print("\nEstadisticas de vr_mov (solo montos validos):")
    print(df[df["vr_mov"] > 0]["vr_mov"].describe())
