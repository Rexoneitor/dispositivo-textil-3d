# -*- coding: utf-8 -*-
"""
Renderiza las vistas de presentacion y tecnicas desde producto_textil.blend (sin interfaz).

  blender -b producto_textil.blend --python render_views.py -- --views 01,08 --samples 128 --scale 100 --out renders

  --views    prefijos numericos separados por coma (por defecto: todas)
  --samples  muestras de Cycles (por defecto las del archivo)
  --scale    porcentaje de resolucion (100 = 1920x1080, 200 = 3840x2160)
  --out      carpeta de salida (relativa al .blend)
  --device   CPU | GPU  (GPU intenta HIP/OPTIX/CUDA y vuelve a CPU si no hay dispositivos)
"""
import bpy
import os
import sys
import time
import importlib.util

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath))
spec = importlib.util.spec_from_file_location("build_device", os.path.join(HERE, "build_device.py"))
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


VIEWS = [
    ("01_presentacion_3Q", "Cam_3Q_Principal", "ensamblado"),
    ("02_vista_frontal", "Cam_Frontal", "ensamblado"),
    ("03_vista_superior", "Cam_Superior", "ensamblado"),
    ("04_vista_lateral", "Cam_Lateral", "ensamblado"),
    ("05_interior_banda", "Cam_Interior", "ensamblado"),
    ("06_detalle_perforaciones", "Cam_Detalle_Perforaciones", "ensamblado"),
    ("07_detalle_union_textil", "Cam_Detalle_Cierre", "ensamblado"),
    ("08_despiece_vertical", "Cam_Despiece_Vertical", "despiece_vertical"),
    ("09_componentes_separados", "Cam_Despiece_Fila", "despiece_fila"),
]

sc = bpy.context.scene
if arg("--samples"):
    sc.cycles.samples = int(arg("--samples"))
sc.render.resolution_percentage = int(arg("--scale", 100))
out = os.path.join(HERE, arg("--out", "renders"))
os.makedirs(out, exist_ok=True)

if arg("--device", "CPU").upper() == "GPU":
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for typ in ("OPTIX", "HIP", "CUDA", "ONEAPI"):
            try:
                prefs.compute_device_type = typ
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type != "CPU"]
                if devs:
                    for d in prefs.devices:
                        d.use = d.type != "CPU"
                    sc.cycles.device = "GPU"
                    print("[RENDER] GPU:", typ, [d.name for d in devs])
                    break
            except Exception:
                continue
    except Exception as ex:
        print("[RENDER] GPU no disponible:", ex)

wanted = arg("--views")
wanted = wanted.split(",") if wanted else None
for name, cam, state in VIEWS:
    if wanted and not any(name.startswith(w) for w in wanted):
        continue
    t0 = time.time()
    bd.set_state(state)
    sc.camera = bpy.data.objects[cam]
    sc.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("[RENDER] %s -> %s (%.1f s)" % (name, sc.render.filepath, time.time() - t0))
bd.set_state("ensamblado")
