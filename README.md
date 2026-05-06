Validación de reglas lógicas de COFOPRI:
1. Reglas de Unidades Administrativas (Prefijo UA)
Analizan la consistencia interna del archivo de Unidades Administrativas.
  •	UA-1001: Dependencia de Partida Registral
    a. Campos Evaluados: Tipo de Documento, Tipo de Partida Registral, Número de Partida Registral.
    b. Condición de Error: El "Número de Partida Registral" está vacío a pesar de que el "Tipo de Documento" y el "Tipo de Partida Registral" sí contienen información.
  •	UA-1002: Coherencia de Clasificación de Casa Habitación
    a. Campos Evaluados: Clasificación Del Predio, Descripción Del Uso.
    b.	Condición de Error: La "Clasificación Del Predio" es CASA HABITACIÓN, pero la "Descripción Del Uso" registra un valor distinto a VIVIENDA.
  •	UA-1003: Validación Lógica de Unidades Físicas (Agrupación por Lote)
    a. Campos Evaluados: Código de Referencia Catastral (CRC), Predio Catastral En, Tipo de Edificación.
    b. Condición de Error:
    c. Si el lote físico tiene exactamente 1 unidad y NO está registrado como PREDIO INDEPENDIENTE.
    d.Si el lote físico tiene más de 1 unidad y SÍ está registrado como PREDIO INDEPENDIENTE.
    e. Excepción/Mensaje: El sistema genera un mensaje de error altamente específico si el "Tipo de Edificación" es CASA/CHALET, para orientar mejor al digitador sobre la naturaleza del inmueble.
  •	UA-1004: Restricción de Casa Habitación en Edificios
    o	Campos Evaluados: Clasificación Del Predio, Predio Catastral En.
    o	Condición de Error: La "Clasificación Del Predio" es CASA HABITACIÓN y simultáneamente está registrado como PREDIO EN EDIFICIO en la columna "Predio Catastral En".
  •	UA-1005: Paquete Obligatorio Registral
    o	Campos Evaluados: Número de Partida Registral, Condición del Titular, Forma de Adquisición, Tipo de Documento, Tipo de Partida Registral.
    o	Condición de Error: Inconsistencia de llenado. Ocurre si el "Número de Partida Registral" tiene datos pero falta alguno de los otros 4 campos; o viceversa (el Número está vacío, pero se registró información en los otros 4).
  •	UA-1006: Validación de Formato y Lógica "Código de Predio"
    o	Campos Evaluados: Número de Partida Registral, Tipo de Partida Registral.
    o	Condición de Error:
    	Contiene caracteres inválidos (solo admite números 0-9, la letra P y comas ,).
    	Si el Número contiene una letra P, el Tipo de Partida DEBE ser estrictamente CÓDIGO DE PREDIO.
  •	UA-1007: Unicidad y Formato del Código de Rentas
    o	Campos Evaluados: Código Contribuyente de Rentas.
    o	Condición de Error: Contiene letras o símbolos (solo admite números y comas) o es un código duplicado asignado a múltiples predios distintos. Se ignoran los valores nulos.
  •	UA-1008: Unicidad y Formato del Código Predial
    o	Campos Evaluados: Código Predial de Rentas.
    o	Condición de Error: Contiene letras o símbolos (solo admite números y comas) o es un código duplicado en la base de datos. Se ignoran los valores nulos.
  •	UA-1009: Unicidad y Formato de la Partida Registral
    o	Campos Evaluados: Número de Partida Registral.
    o	Condición de Error: Contiene caracteres inválidos (solo admite números, la letra P y comas) o el número de partida se encuentra duplicado en otro predio. Se ignoran los valores nulos.
  •	UA-1010: Campos Obligatorios del Titular
    o	Campos Evaluados: Condición del Titular, Forma de Adquisición.
    o	Condición de Error: Cualquiera de estas dos columnas (o ambas) se encuentra completamente vacía.
________________________________________
2. Reglas de Ingresos de Campo (Prefijo IN)
Analizan la consistencia interna del archivo de Ingresos.
  •	IN-1001: Valores Prohibidos en Condición Numérica
    o	Campos Evaluados: Condición Numérica, Número Municipal.
    o	Condición de Error:
    	La "Condición Numérica" contiene los valores prohibidos GEN. POR EL TEC. CAT. o SIN CONDICIÓN.
    	La "Condición Numérica" está vacía Y el "Número Municipal" indica que sí existe un número físico (es decir, es distinto de S/N).
    o	Excepción: Se permite que la Condición Numérica esté vacía si el Número Municipal es S/N.
________________________________________
3. Reglas Relacionales (Cruces entre bases de datos)
Auditan la información cruzando llaves primarias entre dos o más archivos de Excel.
  •	IN-1002: Cruce de Titularidad (Unidades Administrativas vs Ingresos)
    o	Archivos Involucrados: unidades_administrativas.xlsx y ingresos.xlsx.
    o	Llave de Cruce: Código de Referencia Catastral (CRC).
    o	Condición de Error:
    	Filtro en UA: Se aíslan los predios donde el "Código Predial de Rentas" contiene información (y no es solo ceros 000...) Y el "Número de Partida Registral" está vacío o lleno solo de ceros.
    	Validación en IN: Al cruzar esos predios específicos hacia el Excel de Ingresos, la "Condición Numérica" resulta ser distinta a AUTO. GEN POR EL TIT. CAT. o SIN NÚMERO (o no se encuentra el registro en ingresos).
  •	UA-R-1001: Cruce de Interiores (Unidades Administrativas vs Rentas)
    o	Archivos Involucrados: unidades_administrativas.xlsx y rentas.xlsx.
    o	Llave de Cruce: "Código Predial de Rentas" (en UA) y "CODIGO_PREDIO" (en Rentas). Se omiten llaves vacías o compuestas solo por ceros.
    o	Condición de Error: Tras encontrar una coincidencia de código predial en ambos archivos, la columna INTERIOR del archivo de Rentas contiene un dato válido, pero este no coincide exactamente con la columna "Número de Interior" registrada en Unidades Administrativas. (La validación es unidireccional: manda Rentas sobre UA).
    
