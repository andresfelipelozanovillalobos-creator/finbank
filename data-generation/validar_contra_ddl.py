"""
Verificacion previa a la carga: comprueba que los datos generados cumplen
TODAS las restricciones declaradas en ../sql/01_modelo_relacional.sql.

    python validar_contra_ddl.py

Sirve para no descubrir un desbordamiento de NVARCHAR o una violacion de
CHECK a mitad de una carga de 500.000 filas contra Azure SQL. Corre en
segundos y contra el disco, sin tocar la base de datos.

Devuelve codigo 1 si algo fallaria en la carga.
"""
import sys

import pandas as pd

from common import cargar_config, leer

# tabla_logica -> {columna: longitud maxima NVARCHAR declarada en el DDL}
LONGITUDES = {
    "clientes":     {"nomb_cli": 100, "apell_cli": 100, "tip_doc": 10,
                     "num_doc": 20, "cod_segmento": 20, "ciudad_res": 50,
                     "depto_res": 50, "estado_cli": 20, "canal_adquis": 30},
    "productos":    {"cod_prod": 20, "desc_prod": 100, "tip_prod": 50,
                     "estado_prod": 20},
    "sucursales":   {"cod_suc": 20, "nom_suc": 100, "tip_punto": 30,
                     "ciudad": 50, "depto": 50},
    "obligaciones": {"id_oblig": 20, "cod_prod": 20, "calif_riesgo": 10},
    "movimientos":  {"id_mov": 30, "cod_prod": 20, "num_cuenta": 30,
                     "tip_mov": 30, "cod_canal": 30, "cod_ciudad": 50,
                     "cod_estado_mov": 20, "id_dispositivo": 20},
    "comisiones":   {"id_comision": 30, "cod_prod": 20, "tip_comision": 50},
}

# Columnas declaradas NOT NULL en el DDL.
NO_NULOS = {
    "clientes":     ["id_cli", "nomb_cli", "apell_cli", "tip_doc", "num_doc",
                     "fec_nac", "fec_alta", "cod_segmento", "ciudad_res",
                     "estado_cli", "canal_adquis"],
    "productos":    ["cod_prod", "desc_prod", "tip_prod", "tasa_ea",
                     "plazo_max_meses", "cuota_min", "comision_admin", "estado_prod"],
    "sucursales":   ["cod_suc", "nom_suc", "tip_punto", "ciudad", "depto",
                     "latitud", "longitud", "activo"],
    "obligaciones": ["id_oblig", "id_cli", "cod_prod", "vr_aprobado",
                     "vr_desembolsado", "sdo_capital", "vr_cuota",
                     "fec_desembolso", "fec_venc", "dias_mora_act", "num_cuotas_pend"],
    "movimientos":  ["id_mov", "id_cli", "cod_prod", "num_cuenta", "fec_mov",
                     "hra_mov", "vr_mov", "tip_mov", "cod_canal",
                     "cod_ciudad", "cod_estado_mov"],
    "comisiones":   ["id_comision", "id_cli", "cod_prod", "fec_cobro",
                     "vr_comision", "tip_comision", "estado_cobro"],
}

# Llaves primarias declaradas: deben ser unicas.
# movimientos NO aparece: no tiene PK a proposito (lleva duplicados).
PRIMARIAS = {
    "clientes": "id_cli", "productos": "cod_prod", "sucursales": "cod_suc",
    "obligaciones": "id_oblig", "comisiones": "id_comision",
}


def main() -> int:
    cfg = cargar_config()
    dfs = {t: leer(cfg, t) for t in LONGITUDES}
    fallas = []

    print("Validando los datos generados contra sql/01_modelo_relacional.sql\n")

    # --- Longitudes NVARCHAR ------------------------------------------------
    print("Longitudes NVARCHAR:")
    for tabla, columnas in LONGITUDES.items():
        for col, maximo in columnas.items():
            serie = dfs[tabla][col].dropna().astype(str)
            if serie.empty:
                continue
            largo = int(serie.str.len().max())
            if largo > maximo:
                fallas.append(f"{tabla}.{col}: '{largo}' excede NVARCHAR({maximo})")
                print(f"  [FALLA] {tabla}.{col:<16} max {largo} > {maximo}")
    print("  Todas las columnas caben en su NVARCHAR." if not fallas else "")

    # --- NOT NULL -----------------------------------------------------------
    print("\nColumnas NOT NULL:")
    problemas_null = 0
    for tabla, columnas in NO_NULOS.items():
        for col in columnas:
            nulos = int(dfs[tabla][col].isna().sum())
            if nulos:
                fallas.append(f"{tabla}.{col} declarada NOT NULL tiene {nulos} nulos")
                print(f"  [FALLA] {tabla}.{col:<16} {nulos} nulos")
                problemas_null += 1
    if not problemas_null:
        print("  Ninguna columna NOT NULL tiene nulos.")

    # --- PRIMARY KEY / UNIQUE ----------------------------------------------
    print("\nUnicidad de llaves primarias:")
    for tabla, pk in PRIMARIAS.items():
        dup = int(dfs[tabla][pk].duplicated().sum())
        estado = "OK" if dup == 0 else "FALLA"
        print(f"  [{estado:^5}] {tabla}.{pk:<14} duplicados: {dup}")
        if dup:
            fallas.append(f"PK {tabla}.{pk} tiene {dup} duplicados")

    dup_doc = int(dfs["clientes"]["num_doc"].duplicated().sum())
    print(f"  [{'OK' if dup_doc == 0 else 'FALLA':^5}] UQ clientes.num_doc  duplicados: {dup_doc}")
    if dup_doc:
        fallas.append(f"UQ clientes.num_doc tiene {dup_doc} duplicados")

    # movimientos DEBE tener duplicados: es la anomalia 1.
    dup_mov = int(dfs["movimientos"]["id_mov"].duplicated().sum())
    print(f"  [ NOTA] movimientos.id_mov duplicados: {dup_mov} "
          f"(anomalia intencional; por eso la tabla no lleva PK)")
    if dup_mov == 0:
        fallas.append("movimientos no tiene duplicados: falta la anomalia 1")

    # --- CHECK constraints --------------------------------------------------
    print("\nCHECK constraints:")
    cli, prod, suc, obl, com = (dfs["clientes"], dfs["productos"],
                                dfs["sucursales"], dfs["obligaciones"],
                                dfs["comisiones"])
    checks = {
        "CK_clientes_score (150-950)":
            int(((cli["score_buro"].notna()) &
                 (~cli["score_buro"].between(150, 950))).sum()),
        "CK_productos_tasa (0-1)":
            int((~prod["tasa_ea"].between(0, 1)).sum()),
        "CK_sucursales_geo":
            int(((~suc["latitud"].between(-90, 90)) |
                 (~suc["longitud"].between(-180, 180))).sum()),
        "CK_oblig_desembolso":
            int((obl["vr_desembolsado"] > obl["vr_aprobado"]).sum()),
        "CK_oblig_saldo":
            int(((obl["sdo_capital"] > obl["vr_desembolsado"]) |
                 (obl["sdo_capital"] < 0)).sum()),
        "CK_oblig_fechas":
            int((pd.to_datetime(obl["fec_venc"]) <=
                 pd.to_datetime(obl["fec_desembolso"])).sum()),
        "CK_oblig_mora":
            int((obl["dias_mora_act"] < 0).sum()),
        "CK_oblig_cuotas":
            int((obl["num_cuotas_pend"] < 0).sum()),
        "CK_comis_valor (> 0)":
            int((com["vr_comision"] <= 0).sum()),
    }
    for nombre, violaciones in checks.items():
        estado = "OK" if violaciones == 0 else "FALLA"
        print(f"  [{estado:^5}] {nombre:<30} violaciones: {violaciones}")
        if violaciones:
            fallas.append(f"{nombre}: {violaciones} filas la violan")

    # --- FOREIGN KEY declaradas en el DDL -----------------------------------
    print("\nFOREIGN KEY declaradas:")
    fks = {
        "FK_oblig_cliente":  (obl["id_cli"], cli["id_cli"]),
        "FK_oblig_producto": (obl["cod_prod"], prod["cod_prod"]),
        "FK_comis_cliente":  (com["id_cli"], cli["id_cli"]),
        "FK_comis_producto": (com["cod_prod"], prod["cod_prod"]),
    }
    for nombre, (hijo, padre) in fks.items():
        huerfanos = int((~hijo.isin(padre)).sum())
        estado = "OK" if huerfanos == 0 else "FALLA"
        print(f"  [{estado:^5}] {nombre:<20} huerfanos: {huerfanos}")
        if huerfanos:
            fallas.append(f"{nombre}: {huerfanos} huerfanos rechazarian la carga")

    # --- Veredicto ----------------------------------------------------------
    print("\n" + "=" * 66)
    if fallas:
        print(f"{len(fallas)} problema(s) impedirian la carga a Azure SQL:\n")
        for f in fallas:
            print(f"  - {f}")
        return 1
    print("Los datos cumplen el modelo relacional. La carga deberia pasar limpia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
