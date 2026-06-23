# Reglas funcionales de asignaciones (SQLite)

## 1) Estados y transiciones válidas

Estados actuales por manzana:

- `Sin asignar`
- `En proceso`
- `Finalizada`
- `En conflicto`

Transiciones permitidas:

1. `Sin asignar` → `En proceso` (cuando un operario toma la manzana).
2. `En proceso` → `Finalizada` (cierre exitoso).
3. `En proceso` → `En conflicto` (cierre con observaciones/conflicto).

Transiciones **no** permitidas por la lógica actual:

- Asignar una manzana que no esté en `Sin asignar`.
- Cerrar una manzana que no esté en `En proceso`.

## 2) Regla: un operario = una manzana activa

- Activa significa estado `En proceso`.
- Antes de asignar, se valida transaccionalmente que el operario no tenga otra manzana en `En proceso`.
- Si ya tiene una activa, la asignación se rechaza.

## 3) Una manzana puede tener múltiples operarios en historial

- Cada asignación crea un registro en `historial_asignaciones`.
- Al cerrar, ese registro histórico se completa con `estado_fin` y `fecha_cierre`.
- Esto permite trazabilidad completa de múltiples ciclos/operarios a lo largo del tiempo.

## 4) Cierre permitido solo al operario asignado

- Para cerrar una manzana en `En proceso`, el operario solicitante debe coincidir con `operador_activo`.
- Si no coincide, el cierre se rechaza.

## 5) Tratamiento de estado `En conflicto`

- `En conflicto` es un estado final operativo de cierre.
- Al cerrar en `En conflicto`, la manzana deja de estar activa para ese operario.
- El operario queda habilitado para tomar una nueva manzana.

## 6) Estructura de tablas SQLite

### `manzanas`

- `id`
- `poligono`
- `manzana`
- `estado`
- `operador_activo`
- `supervisor_activo`
- `fecha_asignacion_activa`
- `fecha_cierre_activa`
- `created_at`
- `updated_at`
- Restricción: `UNIQUE(poligono, manzana)`

### `lotes`

- `id`
- `manzana_id` (FK a `manzanas.id`)
- `lote`
- `created_at`
- Restricción: `UNIQUE(manzana_id, lote)`

### `historial_asignaciones`

- `id`
- `manzana_id` (FK a `manzanas.id`)
- `poligono`
- `manzana`
- `operador`
- `supervisor`
- `estado_inicio`
- `estado_fin`
- `fecha_asignacion`
- `fecha_cierre`
- `detalle`

## 7) Cómo cambiar reglas en el futuro sin romper datos

1. **No sobrescribir historial**: agregar nuevos eventos/filas en historial en lugar de mutar eventos antiguos.
2. **Migraciones aditivas**: agregar columnas/tablas nuevas y mantener compatibilidad hacia atrás.
3. **Versionar reglas por código**: centralizar estados válidos y transiciones en constantes/funciones de dominio.
4. **Mantener cierres transaccionales**: toda validación de estado + actualización debe ocurrir en una misma transacción.
5. **Evitar claves funcionales volátiles**: conservar `UNIQUE(poligono, manzana)` como llave de negocio estable.

## 8) Checklist de pruebas operativas

- [ ] Cargar Excel con columnas `Poligono`, `Manzana`, `Lote`.
- [ ] Verificar que se inserten nuevas manzanas y lotes, sin duplicados.
- [ ] Asignar una manzana disponible y validar estado `En proceso`.
- [ ] Confirmar notificación Discord al asignar.
- [ ] Intentar asignar segunda manzana al mismo operario y validar bloqueo.
- [ ] Cerrar en `Finalizada` y validar liberación de operario.
- [ ] Cerrar en `En conflicto` y validar liberación de operario.
- [ ] Confirmar notificación Discord al cierre (con estado final).
- [ ] Verificar filtros/KPIs/vista colaborativa en supervisión.
- [ ] Exportar “excel colaborativo” y validar contenido.
