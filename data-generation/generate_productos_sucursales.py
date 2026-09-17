import random
import numpy as np
import pandas as pd
from generate_clientes import cargar_config

# coordenadas del centro de cada ciudad, para ubicar las sucursales
COORDENADAS = {
    "Bogota": (4.7110, -74.0721),
    "Medellin": (6.2442, -75.5812),
    "Cali": (3.4516, -76.5320),
    "Barranquilla": (10.9639, -74.7964),
    "Ciudad de Mexico": (19.4326, -99.1332),
    "Guadalajara": (20.6597, -103.3496),
    "Lima": (-12.0464, -77.0428),
    "Santiago": (-33.4489, -70.6693),
    "Buenos Aires": (-34.6037, -58.3816),
}

# tip_prod, descripcion, rango de tasa EA, familia
CATALOGO = [
    ("Credito Libre Inversion", "Credito de Libre Inversion", (0.18, 0.30), "credito"),
    ("Credito Rotativo", "Cupo Rotativo", (0.25, 0.35), "credito"),
    ("Credito Vehiculo", "Credito de Vehiculo", (0.14, 0.22), "credito"),
    ("Tarjeta Digital", "Tarjeta de Credito Digital", (0.22, 0.32), "credito"),
    ("Cuenta de Ahorro", "Cuenta de Ahorro Digital", (0.00, 0.02), "ahorro"),
    ("CDT", "Certificado de Deposito a Termino", (0.08, 0.13), "ahorro"),
    ("Servicio Transaccional", "Pagos PSE / Transferencias ACH", (0.0, 0.0), "transaccional"),
    ("Corresponsalia", "Servicio de Corresponsalia Bancaria", (0.0, 0.0), "transaccional"),
]

# productos que pueden originar una obligacion
PRODUCTOS_CREDITO = ["Credito Libre Inversion", "Credito Rotativo",
                     "Credito Vehiculo", "Tarjeta Digital"]


def generar_productos(config):
    random.seed(config["seed"] + 1)
    n = config["volumenes"]["productos"]

    registros = []
    for i in range(n):
        # se recorre el catalogo en ciclo para que todas las familias salgan
        tip_prod, desc, rango_tasa, familia = CATALOGO[i % len(CATALOGO)]

        if familia == "credito":
            plazo = random.choice([12, 24, 36, 48, 60])
            cuota_min = round(random.uniform(50000, 300000), -3)
            comision = round(random.uniform(5000, 25000), -2)
        else:
            plazo = 0
            cuota_min = 0.0
            comision = round(random.uniform(0, 8000), -2)

        registros.append({
            "cod_prod": f"PROD-{i+1:03d}",
            "desc_prod": f"{desc} {i+1}",
            "tip_prod": tip_prod,
            "tasa_ea": round(random.uniform(*rango_tasa), 4),
            "plazo_max_meses": plazo,
            "cuota_min": cuota_min,
            "comision_admin": comision,
            "estado_prod": "Activo" if random.random() > 0.05 else "Inactivo",
        })

    return pd.DataFrame(registros)


def generar_sucursales(config):
    random.seed(config["seed"] + 2)
    np.random.seed(config["seed"] + 2)
    n = config["volumenes"]["sucursales"]

    tipos = ["Sucursal Fisica", "Corresponsal Bancario", "Cajero Automatico", "Punto Digital"]
    pesos_tipo = [0.30, 0.35, 0.25, 0.10]

    ciudades = []
    for pais in config["paises"]:
        for ciudad in pais["ciudades"]:
            ciudades.append((ciudad, pais["nombre"]))

    registros = []
    for i in range(n):
        ciudad, pais = random.choice(ciudades)
        tipo = np.random.choice(tipos, p=pesos_tipo)
        lat, lon = COORDENADAS[ciudad]

        registros.append({
            "cod_suc": f"SUC-{i+1:04d}",
            "nom_suc": f"{tipo} {ciudad} {i+1}",
            "tip_punto": tipo,
            "ciudad": ciudad,
            "depto": pais,
            # se dispersan unos km alrededor del centro de la ciudad
            "latitud": round(lat + random.uniform(-0.05, 0.05), 6),
            "longitud": round(lon + random.uniform(-0.05, 0.05), 6),
            "activo": random.random() > 0.03,
        })

    return pd.DataFrame(registros)


if __name__ == "__main__":
    cfg = cargar_config()
    out_dir = cfg["salida"]["directorio"]

    # estos dos catalogos salen en JSON para que la ingesta tenga dos formatos
    df_prod = generar_productos(cfg)
    df_prod.to_json(f"{out_dir}/tb_productos_cat.json", orient="records",
                    indent=2, force_ascii=False)

    df_suc = generar_sucursales(cfg)
    df_suc.to_json(f"{out_dir}/tb_sucursales_red.json", orient="records",
                   indent=2, force_ascii=False)

    print(f"Generados {len(df_prod)} productos -> {out_dir}/tb_productos_cat.json")
    print(df_prod.head(5).to_string())
    print("\nProductos por tipo:")
    print(df_prod["tip_prod"].value_counts())

    print(f"\nGeneradas {len(df_suc)} sucursales -> {out_dir}/tb_sucursales_red.json")
    print(df_suc.head(5).to_string())
    print("\nDistribucion de tip_punto:")
    print(df_suc["tip_punto"].value_counts(normalize=True).round(3))
