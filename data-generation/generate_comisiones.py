import random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from generate_clientes import cargar_config

# cada tipo de comision tiene su peso y su rango de valor:
# una comision de administracion cuesta mas que una consulta de saldo
TIPOS_COMISION = {
    "Comision Administracion": (0.30, 15000, 45000),
    "Comision Manejo Cuenta": (0.25, 8000, 20000),
    "Comision Retiro Cajero": (0.20, 2000, 8000),
    "Comision Transferencia": (0.15, 3000, 12000),
    "Comision Consulta Saldo": (0.10, 500, 2500),
}

ESTADOS = ["Cobrado", "Pendiente", "Rechazado"]
PESOS_ESTADO = [0.85, 0.10, 0.05]


def generar_comisiones(config, df_clientes, df_productos):
    seed = config["seed"]
    random.seed(seed + 5)
    np.random.seed(seed + 5)

    n = config["volumenes"]["comisiones"]
    fecha_inicio = date.fromisoformat(config["periodo"]["fecha_inicio"])
    fecha_fin = date.fromisoformat(config["periodo"]["fecha_fin"])
    dias = (fecha_fin - fecha_inicio).days

    ids_clientes = df_clientes["id_cli"].tolist()
    ids_productos = df_productos["cod_prod"].tolist()

    nombres = list(TIPOS_COMISION.keys())
    pesos = [TIPOS_COMISION[t][0] for t in nombres]

    # la banca liquida al corte de mes, asi que los primeros dias concentran el grueso
    pesos_dia = np.array([3.5 if (fecha_inicio + timedelta(days=i)).day <= 5 else 1.0
                          for i in range(dias + 1)])
    pesos_dia = pesos_dia / pesos_dia.sum()

    registros = []
    for i in range(n):
        tipo = np.random.choice(nombres, p=pesos)
        _, vr_min, vr_max = TIPOS_COMISION[tipo]
        fec = fecha_inicio + timedelta(days=int(np.random.choice(dias + 1, p=pesos_dia)))

        registros.append({
            "id_comision": f"COM-{i+1:06d}",
            "id_cli": random.choice(ids_clientes),
            "cod_prod": random.choice(ids_productos),
            "fec_cobro": fec.isoformat(),
            "vr_comision": round(random.uniform(vr_min, vr_max), -2),
            "tip_comision": tipo,
            "estado_cobro": np.random.choice(ESTADOS, p=PESOS_ESTADO),
        })

    return pd.DataFrame(registros)


if __name__ == "__main__":
    cfg = cargar_config()
    out_dir = cfg["salida"]["directorio"]

    df_clientes = pd.read_csv(f"{out_dir}/tb_clientes_core.csv")
    df_productos = pd.read_json(f"{out_dir}/tb_productos_cat.json")

    df = generar_comisiones(cfg, df_clientes, df_productos)
    df.to_csv(f"{out_dir}/tb_comisiones_log.csv", index=False, encoding="utf-8")

    print(f"Generadas {len(df)} comisiones -> {out_dir}/tb_comisiones_log.csv")
    print(df.head(5).to_string())

    print("\nIntegridad referencial (debe dar 0):")
    print("  id_cli huerfanos:  ", (~df["id_cli"].isin(df_clientes["id_cli"])).sum())
    print("  cod_prod huerfanos:", (~df["cod_prod"].isin(df_productos["cod_prod"])).sum())

    print("\nDistribucion de estado_cobro:")
    print(df["estado_cobro"].value_counts(normalize=True).round(3))

    cobrado = df[df["estado_cobro"] == "Cobrado"]["vr_comision"].sum()
    print(f"\nTotal efectivamente cobrado: ${cobrado:,.0f}")
