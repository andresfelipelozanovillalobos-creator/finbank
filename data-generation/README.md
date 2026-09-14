# Generacion de datos - Fase 1

Escenario A, banca y servicios financieros. Genera las 6 tablas sinteticas
del origen y las carga a Azure SQL Database.

## Como correrlo

```bash
pip install -r requirements.txt

python run_all.py                          # genera todo en output/
cp db_config.example.yaml db_config.yaml   # llenar credenciales
python load_data_to_sql.py                 # crea las tablas y carga
python insertar_datos_incrementales.py     # simula un dia nuevo (opcional)
```

Tambien se puede correr cada generador por separado, pero respetando el
orden, porque cada uno lee las llaves del anterior:

```
generate_clientes.py
generate_productos_sucursales.py
generate_obligaciones.py
generate_movimientos.py
generate_comisiones.py
```

## Tablas

| Tabla | Filas | Formato |
|---|---|---|
| tb_clientes_core | 10.000 | CSV |
| tb_productos_cat | 50 | JSON |
| tb_sucursales_red | 200 | JSON |
| tb_obligaciones | 30.000 | CSV |
| tb_mov_financieros | ~502.500 | CSV |
| tb_comisiones_log | 80.000 | CSV |

Los dos catalogos salen en JSON y el resto en CSV, para que la ingesta
tenga que manejar dos formatos distintos.

El modelo relacional con las PK, FK y CHECK esta en `../sql/01_modelo_relacional.sql`.
`load_data_to_sql.py` ejecuta ese mismo archivo, asi no hay dos versiones del DDL.

## Reproducibilidad

Todo sale de la semilla del `config.yaml` (42 por defecto). Se pasa a
`random`, `numpy` y `Faker`, y cada generador usa un desplazamiento distinto
(seed+1, seed+2...) para que regenerar una tabla no cambie las demas.

Con la misma semilla el resultado es identico:

```bash
python run_all.py && md5sum output/tb_clientes_core.csv
python run_all.py && md5sum output/tb_clientes_core.csv   # mismo hash
```

## Distribuciones

No es data aleatoria plana, cada campo tiene una forma con sentido:

| Campo | Distribucion | Por que |
|---|---|---|
| fec_nac | Normal(38, 12) entre 18 y 80 | edad tipica de la poblacion bancarizada |
| score_buro | Normal(650, 100) entre 150 y 950 | escala real de buro |
| cod_segmento | 45 / 35 / 15 / 5 % | piramide de ingresos |
| vr_mov | Log-normal(10.5, 1.1) | mediana ~36.000, cola larga: muchas compras chicas y pocas transferencias grandes |
| hra_mov | picos 11-13 y 17-19 | horario de almuerzo y de salida |
| fec_mov | estacional, ver abajo | pulso real de un banco |
| dias_mora_act | 80 / 10 / 5 / 3 / 2 % | buckets de cartera |
| calif_riesgo | depende de la mora | a mas mora, mas probabilidad de riesgo alto |

### Estacionalidad de las fechas

El peso de cada dia es el producto de tres factores (esta en
`generate_movimientos.py`):

- mes: diciembre x1.40, enero x0.80, junio x1.10
- dia de la semana: sabado x0.70, domingo x0.45, viernes x1.15
- quincena: dias 15 y 30 x1.70, dias 1, 16 y 31 x1.45

Con eso diciembre queda con casi el doble de movimientos que febrero, y en
el histograma por dia se ven los picos de quincena. La consulta 5 del
`02_verificacion_carga.sql` lo muestra.

Las comisiones tienen su propia estacionalidad: se concentran en los
primeros 5 dias del mes, que es cuando la banca liquida.

## Anomalias

Las cuatro estan concentradas en `tb_mov_financieros`. `tb_comisiones_log`
queda limpia a proposito, para poder comprobar que el pipeline de calidad
no marque falsos positivos.

| Anomalia | Como se genera | Filas | Como detectarla |
|---|---|---|---|
| Duplicados exactos | se repite la fila completa, con el mismo id_mov | 2.500 | `GROUP BY id_mov HAVING COUNT(*) > 1` |
| Fechas fuera de rango | anios 2005-2014 o 2030 | ~1.500 | `fec_mov` fuera del periodo |
| id_cli huerfanos | id por encima del maximo real | ~2.500 | `LEFT JOIN` contra clientes da NULL |
| Montos invalidos | vr_mov en 0 o negativo | ~1.500 | `vr_mov <= 0` |

Los porcentajes se cambian desde `anomalias` en el `config.yaml`.

**Por que tb_mov_financieros no tiene PK ni FK:** es la tabla de aterrizaje.
Si el motor rechazara los duplicados y los huerfanos, esos datos nunca
llegarian y el pipeline de calidad no tendria nada que detectar. Las
constraints se aplican al pasar a Silver. Las demas tablas si las tienen.

## Nulos

Un 5% en campos no criticos, nunca en llaves ni en montos:

- `clientes.score_buro`: cliente sin historial crediticio
- `clientes.depto_res`: direccion incompleta al momento del alta
- `obligaciones.calif_riesgo`: obligacion recien originada, sin calificar
- `movimientos.id_dispositivo`: transaccion hecha en ventanilla

## Para la carga a Azure

1. ODBC Driver 18 for SQL Server instalado (no se instala con pip).
2. La IP publica habilitada en el firewall del SQL Server en Azure.
3. `db_config.yaml` lleno. Ese archivo esta en el `.gitignore`.
