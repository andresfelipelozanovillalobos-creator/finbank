"""
Corre los cinco generadores en orden y al final valida el resultado.
El orden importa: cada tabla lee las llaves de la anterior.

    python run_all.py
"""
import os
import time
import pandas as pd

from generate_clientes import cargar_config, generar_clientes
from generate_productos_sucursales import generar_productos, generar_sucursales
from generate_obligaciones import generar_obligaciones
from generate_movimientos import generar_movimientos
from generate_comisiones import generar_comisiones


def validar(cfg, out_dir, clientes, productos, obligaciones, movimientos, comisiones):
    print("\n" + "-" * 60)
    print("VALIDACION DEL DATASET")
    print("-" * 60)

    print("\nFilas por tabla:")
    for nombre, df in [("tb_clientes_core", clientes),
                       ("tb_productos_cat", productos),
                       ("tb_obligaciones", obligaciones),
                       ("tb_mov_financieros", movimientos),
                       ("tb_comisiones_log", comisiones)]:
        print(f"  {nombre:<22} {len(df):>9,}")

    print("\nIntegridad referencial (debe dar 0):")
    revisiones = [
        ("obligaciones.id_cli", obligaciones["id_cli"], clientes["id_cli"]),
        ("obligaciones.cod_prod", obligaciones["cod_prod"], productos["cod_prod"]),
        ("comisiones.id_cli", comisiones["id_cli"], clientes["id_cli"]),
        ("comisiones.cod_prod", comisiones["cod_prod"], productos["cod_prod"]),
        ("movimientos.cod_prod", movimientos["cod_prod"], productos["cod_prod"]),
    ]
    for nombre, hijo, padre in revisiones:
        print(f"  {nombre:<24} {(~hijo.isin(padre)).sum()}")

    print("\nNulos en campos no criticos (se busca ~5%):")
    print(f"  clientes.score_buro        {clientes['score_buro'].isna().mean():.2%}")
    print(f"  clientes.depto_res         {clientes['depto_res'].isna().mean():.2%}")
    print(f"  obligaciones.calif_riesgo  {obligaciones['calif_riesgo'].isna().mean():.2%}")
    print(f"  movimientos.id_dispositivo {movimientos['id_dispositivo'].isna().mean():.2%}")

    print("\nLlaves primarias duplicadas (debe dar 0, menos movimientos):")
    print(f"  clientes.id_cli        {clientes['id_cli'].duplicated().sum()}")
    print(f"  obligaciones.id_oblig  {obligaciones['id_oblig'].duplicated().sum()}")
    print(f"  comisiones.id_comision {comisiones['id_comision'].duplicated().sum()}")

    fechas = pd.to_datetime(movimientos["fec_mov"])
    validas = fechas[(fechas.dt.year >= 2015) & (fechas.dt.year <= 2027)]
    por_mes = validas.dt.to_period("M").value_counts()
    print(f"\nCobertura temporal: {por_mes.size} meses "
          f"({validas.min().date()} a {validas.max().date()})")
    print(f"  mes mas alto: {por_mes.idxmax()} con {por_mes.max():,}")
    print(f"  mes mas bajo: {por_mes.idxmin()} con {por_mes.min():,}")

    print("\nAnomalias intencionales en movimientos:")
    print(f"  duplicados exactos:    {movimientos['id_mov'].duplicated().sum():>7,}")
    print(f"  fechas fuera de rango: {((fechas.dt.year < 2015) | (fechas.dt.year > 2027)).sum():>7,}")
    print(f"  id_cli huerfanos:      {(~movimientos['id_cli'].isin(clientes['id_cli'])).sum():>7,}")
    print(f"  montos invalidos:      {(movimientos['vr_mov'] <= 0).sum():>7,}")

    archivos = sorted(os.listdir(out_dir))
    formatos = sorted({a.split(".")[-1] for a in archivos})
    print(f"\nFormatos de salida: {', '.join(formatos)}")


if __name__ == "__main__":
    inicio = time.time()
    cfg = cargar_config()
    out_dir = cfg["salida"]["directorio"]
    os.makedirs(out_dir, exist_ok=True)

    print(f"Semilla {cfg['seed']} | periodo {cfg['periodo']['fecha_inicio']} "
          f"a {cfg['periodo']['fecha_fin']}\n")

    print("1/5 clientes...")
    clientes = generar_clientes(cfg)
    clientes.to_csv(f"{out_dir}/tb_clientes_core.csv", index=False, encoding="utf-8")

    print("2/5 productos y sucursales...")
    productos = generar_productos(cfg)
    productos.to_json(f"{out_dir}/tb_productos_cat.json", orient="records",
                      indent=2, force_ascii=False)
    sucursales = generar_sucursales(cfg)
    sucursales.to_json(f"{out_dir}/tb_sucursales_red.json", orient="records",
                       indent=2, force_ascii=False)

    print("3/5 obligaciones...")
    obligaciones = generar_obligaciones(cfg, clientes, productos)
    obligaciones.to_csv(f"{out_dir}/tb_obligaciones.csv", index=False, encoding="utf-8")

    print("4/5 movimientos...")
    movimientos = generar_movimientos(cfg, clientes, productos)
    movimientos.to_csv(f"{out_dir}/tb_mov_financieros.csv", index=False, encoding="utf-8")

    print("5/5 comisiones...")
    comisiones = generar_comisiones(cfg, clientes, productos)
    comisiones.to_csv(f"{out_dir}/tb_comisiones_log.csv", index=False, encoding="utf-8")

    validar(cfg, out_dir, clientes, productos, obligaciones, movimientos, comisiones)
    print(f"\nListo en {time.time() - inicio:.1f} segundos. Archivos en {out_dir}")
