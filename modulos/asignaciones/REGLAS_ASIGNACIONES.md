# Reglas funcionales del módulo de asignaciones

## 1) Estados y transiciones válidas
Estados de manzana:
- `Sin asignar`
- `En proceso`
- `Finalizada`
- `En conflicto`

Transiciones permitidas:
- `Sin asignar` -> `En proceso` (asignación)
- `En conflicto` -> `En proceso` (reasignación)
- `En proceso` -> `Finalizada` (cierre exitoso)
- `En proceso` -> `En conflicto` (cierre con conflicto)

Transiciones no permitidas:
- Cualquier cierre desde estados distintos de `En proceso`.
- Cierre por operador diferente al asignado actualmente.

## 2) Regla de un operario = una manzana activa
Un operario solo puede tener una manzana en estado `En proceso` a la vez.
Antes de asignar, el sistema valida en transacción si ya existe otra manzana activa para ese operario.

## 3) Una manzana puede tener múltiples operarios en historial
La tabla `historial_asignaciones` registra cada ciclo de asignación/cierre.
Por ello una misma manzana puede haber sido trabajada por varios operarios en distintos momentos, sin perder trazabilidad.

## 4) Cierre permitido solo al operario asignado
En el cierre se valida:
- que la manzana esté en `En proceso`
- que `operador_activo` sea el mismo operario que intenta cerrar

Si no se cumple, el cierre se rechaza.

## 5) Tratamiento de `En conflicto`
Cuando una manzana se cierra como `En conflicto`:
- se libera el operario (`operador_activo = NULL`)
- el operario puede tomar otra manzana inmediatamente
- la manzana queda disponible para una futura reasignación

## 6) Estructura de tablas SQLite
Base: `Repositorio_de_Asignaciones/asignaciones.db`

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
- `UNIQUE(poligono, manzana)`

### `lotes`
- `id`
- `manzana_id`
- `lote`
- `created_at`
- `UNIQUE(manzana_id, lote)`

### `historial_asignaciones`
- `id`
- `manzana_id`
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
1. No eliminar columnas históricas ni sobreescribir eventos pasados.
2. Agregar nuevos estados solo si se definen transiciones explícitas y validaciones en `storage.py`.
3. Mantener trazabilidad insertando nuevos eventos en `historial_asignaciones` en cada transición.
4. Para cambios de esquema, usar migraciones aditivas (crear columnas/tablas nuevas) y scripts de backfill si hace falta.
5. Conservar `UNIQUE(poligono, manzana)` y `UNIQUE(manzana_id, lote)` para evitar duplicados de negocio.

## 8) Checklist de pruebas operativas
- [ ] Cargar Excel con columnas `Poligono`, `Manzana`, `Lote`.
- [ ] Ver manzanas en estado `Sin asignar` en la UI.
- [ ] Asignar manzana y validar estado `En proceso`.
- [ ] Confirmar envío de notificación Discord al asignar.
- [ ] Intentar asignar segunda manzana al mismo operario y validar bloqueo.
- [ ] Cerrar manzana con `Finalizada` y validar notificación Discord.
- [ ] Cerrar manzana con `En conflicto` y verificar que el operario pueda tomar otra.
- [ ] Ver KPIs y tabla de supervisión con filtros por polígono/estado/operario.
- [ ] Exportar “excel colaborativo” y verificar hojas de estado y avance.
