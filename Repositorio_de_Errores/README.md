# Repositorio de Errores

Esta carpeta contiene los archivos Excel con los validadores de errores generados desde los backups de la base de datos.

## Estructura
- Coloca aquí los archivos `.xlsx` o `.xlsb` que contienen los errores por validador
- Cada archivo puede tener múltiples hojas, una por cada tipo de error
- El sistema cargará automáticamente todos los archivos en esta carpeta

## Formato esperado
- **Columnas requeridas**: Sector, Manzana, Lote (o similar) + detalles del error
- **Columna Estado**: Se agregará automáticamente con valores "Corregido" o "No corregido"

## Ejemplo de archivo
```
Archivo: Validadores_Puertas.xlsx
  - Hoja 1: Puerta sin número
  - Hoja 2: Puerta dañada
  - Hoja 3: Puerta mal identificada
```

Cada error se puede marcar como Corregido en la interfaz de Streamlit y los cambios se guardarán automáticamente.
