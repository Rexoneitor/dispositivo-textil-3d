# Dispositivo textil circular — modelo 3D parametrico (Blender 5.2)

## 1. Interpretacion del diseno (a partir de los dos bocetos)
Anillo abierto con zona de cierre frontal, formado por tres componentes independientes:

| | Componente | Interpretacion |
|---|---|---|
| **A** | Neopreno perforado | Banda curva en anillo abierto (extremos separados hacia +Y), espesor real, extremos reforzados, perforaciones pasantes en geometria real con chaflan. |
| **B** | Cinta / lamina de poliester | Pieza independiente en forma de "I" (dos barras horizontales unidas por un alma central), curvada sobre la cara exterior del neopreno, con costura perimetral. En el boceto 2 aparece como una "I" con una flecha: se interpreto como pieza que envuelve el frente. |
| **C** | Licra con velcro medico | Cuerpo rectangular de licra sobre el frente + solapa superior mas estrecha (el boceto 3 muestra un rectangulo con un tab superior). Zona de **bucles** en el cuerpo y de **ganchos** (tipo seta) en la solapa, ambos con geometria real sobre bases tejidas. |

## 2. Supuestos y dimensiones PROVISIONALES (los bocetos no tienen escala)
- Diametro interior 180 mm · anchura de banda 46 mm · espesor neopreno 4.5 mm (refuerzo de extremos hasta 8.5 mm).
- Abertura entre extremos 34 grados (centrada en +Y); el frente (cierre) esta en -Y.
- 80 perforaciones (4 filas, diametro 6.0 mm, paso 12.5 mm) fuera de la zona frontal y de los refuerzos.
- Poliester: 1.2 mm; arco frontal de +-52 grados; barras de 10 mm.
- Licra: 1.6 mm; cuerpo de ~76 mm de arco x 50 mm; solapa 14 grados de semi-arco, hasta z = 38.5 mm.
- Velcro: paso 1.15 mm; ~208 ganchos y ~816 bucles modelados.
- Los colores (neopreno negro, poliester azul grisaceo, licra grafito, bucles beige, ganchos crema) son supuestos: los bocetos son monocromos.
- No se modelan ni se afirman resistencia, capacidad de carga ni propiedades medicas.

## 3. Archivos
- `build_device.py` — script completo y reproducible (crea todo, ejecuta el control de calidad y guarda el .blend).
- `producto_textil.blend` — archivo generado (10 colecciones 00_ ... 09_, materiales procedurales, 9 camaras, luces de estudio).
- `render_views.py` — renderiza las 9 vistas desde linea de comandos.
- `renders/` — imagenes finales 1920x1080. `reporte_validacion.md` — informe tecnico. `referencias/` — bocetos originales (tambien empaquetados en el .blend).

## Modelos 3D exportados (carpeta `exportados/`)
- `dispositivo_textil.glb` — glTF binario con materiales (web/three.js, Unity, Unreal, visores 3D). Eje Y arriba.
- `dispositivo_textil.obj` + `.mtl` — malla universal con materiales basicos.
- `dispositivo_textil.stl` — solo geometria (impresion 3D / CAD).
- 11 objetos (A: neopreno; B: lamina y costuras; C: licra, solapa, velcro y costuras), ~106 000 vertices,
  unidades en metros, modificadores aplicados (perforaciones incluidas). Regenerar: `blender -b producto_textil.blend --python export_models.py`.
- Las texturas procedurales (trama, espuma) no viajan en GLB/OBJ: alli solo van colores y rugosidad.

## Como ver el modelo al abrir el .blend
- El archivo se abre en la camara principal con vista **Solid** (colores de material, sombras y cavidades).
- Aspecto fotorrealista: pulsar **F12** (render Cycles) o ver las imagenes de `renders/`.
- En este equipo (grafica integrada AMD) la vista **Material Preview / EEVEE provoca un cierre de Blender**
  (`eevee::LightModule`); por eso no se usa como vista por defecto. En equipos con GPU dedicada funciona con normalidad.

## 4. Como modificar el modelo
1. En Blender, seleccionar el vacio **CTRL_Parametros** (coleccion `09_CONTROLES_PARAMETRICOS`) > pestana *Object Properties* > *Custom Properties*.
2. Editar valores en metros/grados (p. ej. `inner_diameter`, `band_width`, `neo_thickness`, `gap_angle`, `holes_rows`, `hole_diameter`, `hole_pitch`, `poly_half_arc_deg`, `lycra_half_arc_deg`, `velcro_pitch`, `stitch_intensity`, `texture_scale`, `explode_dist`...).
3. Volver a ejecutar `build_device.py` (Scripting > Run Script). Regenera perforaciones, cierre y demas piezas sin duplicar objetos.
4. Apertura del anillo: `gap_angle`. Perforaciones: `holes_rows`, `hole_diameter`, `hole_pitch`, `hole_row_pitch`, `hole_front_clear_deg`.
5. Perforaciones en vivo: el modificador Boolean de `A_Neopreno_Banda` usa el objeto oculto `A_Cortadores_Perforaciones` (se puede mover/borrar cortadores a mano).
6. Vistas: en consola, `import build_device as bd; bd.set_state("ensamblado" | "despiece_vertical" | "despiece_fila")`.
7. Render: `blender -b producto_textil.blend --python render_views.py -- --samples 256 --scale 200 --out renders_4k` (4K con `--scale 200`; `--device GPU` intenta usar GPU).

Nota: tras cambiar valores por defecto dentro del script, borre antes el vacio CTRL_Parametros, porque sus valores guardados tienen prioridad.
