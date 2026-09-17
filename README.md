# finbank

Prueba técnica  dataNow

# Escenario Elegido
FinBank S.A. es un banco digital fundado en 2015 con presencia en cinco países de Latinoamérica:
Colombia, Mexico, Peru, Chile y Argentina. Opera exclusivamente a través de canales digitales —
aplicación móvil, portal web y una red de corresponsales bancarios — y cuenta con más de dos
millones de clientes activos. Su cartera de crédito supera los USD 800 millones y el banco procesa
en promedio 1.2 millones de transacciones diarias entre pagos, transferencias, recargas y avances.
El modelo de negocio se basa en tres líneas de producto: crédito de consumo (créditos de libre
inversión, crédito rotativo y tarjeta digital), cuentas de ahorro digitales y servicios transaccionales
como pagos PSE, transferencias ACH y corresponsalía. La base de clientes esta segmentada
internamente en cuatro categorías: básico para ingresos inferiores a dos salarios mínimos, estándar
entre dos y cinco, Premium entre cinco y quince, y Elite para clientes de alto patrimonio.
El equipo de Riesgo Crediticio, compuesto por doce analistas y tres científicos de datos, monitorea
diariamente el comportamiento de la cartera y calcula las provisiones regulatorias exigidas por la
Superintendencia Financiera. Hoy trabaja con reportes manuales en Excel construidos cada mañana
durante dos horas a partir de múltiples bases desconectadas, lo que genera inconsistencias, retrasos
y riesgo operativo. El área de prevención de Fraude opera en paralelo con reglas manuales que
requieren ser enriquecidas con señales históricas del comportamiento del cliente. La necesidad
central es un pipeline que consolide toda esta información para que ambos equipos consuman datos
confiables y actualizados sin procesos manuales


# Plataforma seleccionada

Microsoft Azure: Se seleccionó Azure debido a que era el entorno cloud con el que se tenía mayor acercamiento previo y documentación disponible, lo que permitió aprovechar mejor el tiempo asignado a la prueba técnica, enfocándose en la implementación de la solución y el aprendizaje específico de los servicios requeridos, en lugar de iniciar desde cero con una plataforma diferente.


# se genera masivamente python

Distribuciones realistas: los datos no deben ser completamente aleatorios. Por ejemplo, las
ventas deben concentrarse en horarios pico, las edades deben seguir una distribución normal,
y los montos de transacciones deben reflejar comportamientos típicos del sector.
• Integridad referencial: todos los identificadores presentes en las tablas de hechos deben
existir en las tablas de dimensiones correspondientes.
• Valores nulos controlados: incluir aproximadamente un cinco por ciento de valores nulos
en campos no críticos para simular condiciones reales de calidad de datos.
• Cobertura temporal: los datos deben cubrir al menos doce meses de histórico con
distribución uniforme o estacional según el sector

<img width="751" height="470" alt="image" src="https://github.com/user-attachments/assets/ac276a93-a7e8-4dae-8270-83ba556f657f" />


# se valida los registros en la nube de azure

<img width="1964" height="1089" alt="image" src="https://github.com/user-attachments/assets/c9f1241f-e81a-489a-9e52-e37c167df516" />

<img width="1178" height="616" alt="image" src="https://github.com/user-attachments/assets/c9bce4e1-6703-49e1-a872-7c167a307a6f" />

# se implementa arquitectura medallon 
<img width="2392" height="939" alt="image" src="https://github.com/user-attachments/assets/f34b4ae4-a71d-45ba-b3e0-0489dc5897e8" />


## Arquitectura de datos

La solución implementa una arquitectura Medallón sobre Azure, utilizando Azure Data Factory para la ingesta de información, Azure Data Lake Storage Gen2 como repositorio central y Azure Databricks para los procesos de transformación y procesamiento distribuido.

### Flujo de datos

1. **Ingesta (Bronze)**
   
   Azure Data Factory realiza la extracción de los archivos fuente y los almacena en la capa Bronze de ADLS Gen2, conservando los datos originales para trazabilidad y auditoría.

   Fuentes cargadas:
   - TB_CLIENTES_CORE
   - TB_COMISIONES_LOG
   - TB_MOV_FINANCIEROS
   - TB_OBLIGACIONES
   - TB_PRODUCTOS_CAT
   - TB_SUCURSALES_RED
  
  <img width="2512" height="1390" alt="image" src="https://github.com/user-attachments/assets/88821f3f-01d6-40ae-a2a7-264819ecf824" />

  <img width="2540" height="786" alt="image" src="https://github.com/user-attachments/assets/d44aac24-01f5-4eeb-bd94-23b1b6f17972" />













