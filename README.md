# Dispositivo Textil Circular — Modelo 3D Paramétrico (Blender API / Python)

Generación automatizada y procedimental de un dispositivo textil médico/deportivo en **Blender 5.2** mediante scripts en Python (`bpy`).

El proyecto demuestra la construcción completa de mallas 3D complejas a partir de bocetos conceptuales sin escala: cálculo de curvaturas, generación de perforaciones por operaciones booleanas, modelado de bucles/ganchos de velcro y automatización de renders por línea de comandos.

---

## 📷 Renders del Modelo Generado

Los renders finales a resolución completa se encuentran disponibles en la carpeta [`renders/`](renders/):

- `01_presentacion_3Q.png`: vista de presentación en tres cuartos.
- `02_vista_frontal.png`: vista frontal.
- `03_vista_superior.png`: vista superior.
- `04_vista_lateral.png`: vista lateral.
- `05_interior_banda.png`: interior de la banda.
- `06_detalle_perforaciones.png`: detalle de las perforaciones.
- `07_detalle_union_textil.png`: detalle de la unión textil.
- `08_despiece_vertical.png`: despiece vertical.
- `09_componentes_separados.png`: componentes separados.

---

## 🛠️ Estructura de Componentes

| Componente | Material | Descripción técnica |
|---|---|---|
| **A** | Neopreno perforado | Banda curva en anillo abierto, espesor calibrado, extremos reforzados con chaflán y perforaciones pasantes en geometría real. Su número depende de los parámetros `holes_rows` y `hole_pitch`. |
| **B** | Cinta de poliéster | Refuerzo estructural curvado sobre la cara exterior del neopreno con costura perimetral. |
| **C** | Licra con velcro | Cuerpo rectangular frontal con zona de micro-bucles y solapa superior con ganchos mecánicos modelados en geometría real. |

---

## 📁 Archivos del Proyecto

- `build_device.py`: Script principal ejecutable dentro de Blender. Construye la geometría completa, asigna materiales procedurales, ejecuta pruebas de control de calidad y configura iluminación de estudio y cámaras.
- `render_views.py`: Automatización de renderizado por lotes desde la terminal para las diferentes cámaras.
- `export_models.py`: Exportador automatizado a formatos estándar.
- `reporte_validacion.md`: Informe técnico de comprobación geométrica y validación de diseño.
- `exportados/`: Modelos generados listos para visualización (`.glb`, `.obj`, `.stl`).
- `renders/`: Imágenes finales generadas con el motor Cycles.

---

## ⚙️ Generación y Ejecución

Para ejecutar la generación paramétrica de forma desatendida desde la terminal:

```bash
# Ejecutar construcción y regeneración del modelo
blender --background --python build_device.py

# Renderizar todas las vistas configuradas
blender --background --python render_views.py
```

### Modificación de Parámetros

El script expone controles paramétricos a través de propiedades personalizadas (`CTRL_Parametros`):
- `inner_diameter`, `band_width`, `neo_thickness`: Dimensiones base del cuerpo textil.
- `gap_angle`: Ángulo de apertura del anillo abierto.
- `holes_rows`, `hole_diameter`, `hole_pitch`: Densidad, diámetro y distribución de perforaciones.
- `velcro_pitch`: Densidad del mallado de bucles y ganchos.
