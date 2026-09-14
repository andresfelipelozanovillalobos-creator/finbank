import os
import random
import yaml
import numpy as np
import pandas as pd
from datetime import date, timedelta
from faker import Faker


def cargar_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generar_clientes(config):
    seed = config["seed"]
    random.seed(seed)
    np.random.seed(seed)
    fake = Faker("es_CO")
    Faker.seed(seed)

    n = config["volumenes"]["clientes"]
    fecha_inicio = date.fromisoformat(config["periodo"]["fecha_inicio"])
    fecha_fin = date.fromisoformat(config["periodo"]["fecha_fin"])
    dias = (fecha_fin - fecha_inicio).days

    # segmentos: piramide de ingresos, la mayoria en los segmentos bajos
    segmentos = ["Basico", "Estandar", "Premium", "Elite"]
    pesos_segmento = [0.45, 0.35, 0.15, 0.05]

    # ciudades ponderadas: 45% Colombia, el resto repartido entre los otros paises
    ciudades = []
    pesos_ciudad = []
    otros = len(config["paises"]) - 1
    for pais in config["paises"]:
        peso = 0.45 if pais["nombre"] == "Colombia" else 0.55 / otros
        for ciudad in pais["ciudades"]:
            ciudades.append((ciudad, pais["nombre"]))
            pesos_ciudad.append(peso / len(pais["ciudades"]))
    pesos_ciudad = np.array(pesos_ciudad) / sum(pesos_ciudad)

    # edad normal centrada en 38, recortada al rango bancarizable
    edades = np.random.normal(38, 12, n)
    edades = np.clip(edades, 18, 80).astype(int)

    # score de buro normal, escala real de 150 a 950
    scores = np.random.normal(650, 100, n)
    scores = np.clip(scores, 150, 950).astype(int)

    canales = ["App Movil", "Portal Web", "Corresponsal Bancario", "Oficina"]

    registros = []
    for i in range(n):
        idx = np.random.choice(len(ciudades), p=pesos_ciudad)
        ciudad, pais = ciudades[idx]

        fec_nac = fecha_fin - timedelta(days=int(edades[i]) * 365 + random.randint(0, 364))
        fec_alta = fecha_inicio + timedelta(days=random.randint(0, dias))

        registros.append({
            "id_cli": 100000 + i,
            "nomb_cli": fake.first_name(),
            "apell_cli": fake.last_name(),
            "tip_doc": "CC",
            "num_doc": fake.unique.numerify("##########"),
            "fec_nac": fec_nac.isoformat(),
            "fec_alta": fec_alta.isoformat(),
            "cod_segmento": np.random.choice(segmentos, p=pesos_segmento),
            "score_buro": int(scores[i]),
            "ciudad_res": ciudad,
            "depto_res": pais,
            "estado_cli": "Activo" if random.random() > 0.03 else "Inactivo",
            "canal_adquis": random.choice(canales),
        })

    df = pd.DataFrame(registros)

    # nulos en campos no criticos: un cliente puede no tener score de buro
    # y la direccion puede quedar incompleta al momento del alta
    pct = config["calidad"]["pct_nulos"]
    for col in ["score_buro", "depto_res"]:
        idx_nulos = df.sample(frac=pct, random_state=seed).index
        df.loc[idx_nulos, col] = None

    return df


if __name__ == "__main__":
    cfg = cargar_config()
    df = generar_clientes(cfg)

    out_dir = cfg["salida"]["directorio"]
    os.makedirs(out_dir, exist_ok=True)
    ruta = f"{out_dir}/tb_clientes_core.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")

    print(f"Generados {len(df)} clientes -> {ruta}")
    print(df.head(5).to_string())

    print("\nNulos por columna:")
    print(df.isnull().sum())

    print("\nDistribucion de segmento:")
    print(df["cod_segmento"].value_counts(normalize=True).round(3))

    print(f"\nDocumentos unicos: {df['num_doc'].nunique()} de {len(df)}")
