import random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from generate_clientes import cargar_config
from generate_productos_sucursales import PRODUCTOS_CREDITO

# buckets de mora tipicos de cartera: dia_min, dia_max, peso
BUCKETS = [
    (0, 0, 0.80),
    (1, 30, 0.10),
    (31, 60, 0.05),
    (61, 90, 0.03),
    (91, 365, 0.02),
]

# a mayor mora, mas probabilidad de riesgo alto
RIESGO = {
    0: [0.85, 0.13, 0.02],
    1: [0.30, 0.55, 0.15],
    2: [0.15, 0.45, 0.40],
    3: [0.08, 0.32, 0.60],
    4: [0.05, 0.25, 0.70],
}


def generar_obligaciones(config, df_clientes, df_productos):
    seed = config["seed"]
    random.seed(seed + 3)
    np.random.seed(seed + 3)

    n = config["volumenes"]["obligaciones"]
    fecha_inicio = date.fromisoformat(config["periodo"]["fecha_inicio"])
    fecha_fin = date.fromisoformat(config["periodo"]["fecha_fin"])
    dias = (fecha_fin - fecha_inicio).days

    ids_clientes = df_clientes["id_cli"].tolist()

    # solo los productos de credito generan obligacion, una cuenta de ahorro no
    productos = df_productos[df_productos["tip_prod"].isin(PRODUCTOS_CREDITO)]
    productos = productos[["cod_prod", "plazo_max_meses"]].to_dict("records")
    if not productos:
        raise ValueError("No hay productos de credito, corre primero generate_productos_sucursales.py")

    calificaciones = ["Bajo", "Medio", "Alto"]
    pesos_bucket = [b[2] for b in BUCKETS]

    registros = []
    for i in range(n):
        prod = random.choice(productos)
        plazo = int(prod["plazo_max_meses"]) or 24

        vr_aprobado = round(random.uniform(1000000, 50000000), -3)
        vr_desembolsado = round(vr_aprobado * random.uniform(0.85, 1.0), -3)

        fec_desembolso = fecha_inicio + timedelta(days=random.randint(0, dias))
        fec_venc = fec_desembolso + timedelta(days=plazo * 30)

        # se asume una cuota mensual desde el desembolso
        meses_pagados = min(plazo, max(0, (fecha_fin - fec_desembolso).days // 30))
        pct_pagado = min(0.95, meses_pagados / plazo)  # nunca se salda del todo
        sdo_capital = round(vr_desembolsado * (1 - pct_pagado), -3)
        cuotas_pend = plazo - meses_pagados

        vr_cuota = round(vr_desembolsado / plazo * random.uniform(1.02, 1.08), -2)

        b = np.random.choice(len(BUCKETS), p=pesos_bucket)
        dias_mora = random.randint(BUCKETS[b][0], BUCKETS[b][1])
        calif = np.random.choice(calificaciones, p=RIESGO[b])

        registros.append({
            "id_oblig": f"OBL-{i+1:06d}",
            "id_cli": random.choice(ids_clientes),
            "cod_prod": prod["cod_prod"],
            "vr_aprobado": vr_aprobado,
            "vr_desembolsado": vr_desembolsado,
            "sdo_capital": sdo_capital,
            "vr_cuota": vr_cuota,
            "fec_desembolso": fec_desembolso.isoformat(),
            "fec_venc": fec_venc.isoformat(),
            "dias_mora_act": dias_mora,
            "num_cuotas_pend": cuotas_pend,
            "calif_riesgo": calif,
        })

    df = pd.DataFrame(registros)

    # una obligacion recien originada puede no tener calificacion todavia
    idx_nulos = df.sample(frac=config["calidad"]["pct_nulos"], random_state=seed + 3).index
    df.loc[idx_nulos, "calif_riesgo"] = None

    return df


if __name__ == "__main__":
    cfg = cargar_config()
    out_dir = cfg["salida"]["directorio"]

    df_clientes = pd.read_csv(f"{out_dir}/tb_clientes_core.csv")
    df_productos = pd.read_json(f"{out_dir}/tb_productos_cat.json")

    df = generar_obligaciones(cfg, df_clientes, df_productos)
    df.to_csv(f"{out_dir}/tb_obligaciones.csv", index=False, encoding="utf-8")

    print(f"Generadas {len(df)} obligaciones -> {out_dir}/tb_obligaciones.csv")
    print(df.head(5).to_string())

    print("\nIntegridad referencial (debe dar 0):")
    print("  id_cli huerfanos:  ", (~df["id_cli"].isin(df_clientes["id_cli"])).sum())
    print("  cod_prod huerfanos:", (~df["cod_prod"].isin(df_productos["cod_prod"])).sum())

    print("\nConsistencia financiera (debe dar 0):")
    print("  desembolsado > aprobado:", (df["vr_desembolsado"] > df["vr_aprobado"]).sum())
    print("  saldo > desembolsado:   ", (df["sdo_capital"] > df["vr_desembolsado"]).sum())
    print("  cuotas pendientes < 0:  ", (df["num_cuotas_pend"] < 0).sum())

    print("\nDistribucion de mora:")
    bins = [-1, 0, 30, 60, 90, 100000]
    labels = ["Al dia", "1-30", "31-60", "61-90", "Mas de 90"]
    print(pd.cut(df["dias_mora_act"], bins=bins, labels=labels).value_counts(normalize=True).round(3))

    print(f"\nSaldo de capital total: ${df['sdo_capital'].sum():,.0f}")
