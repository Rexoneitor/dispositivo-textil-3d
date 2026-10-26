# -*- coding: utf-8 -*-
"""Exporta el ensamblaje (A, B, C) a GLB, OBJ y STL.  Uso: blender -b producto_textil.blend --python export_models.py"""
import bpy
import os

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath))
OUT = os.path.join(HERE, "exportados")
os.makedirs(OUT, exist_ok=True)

cols = ["01_NEOPRENO_PERFORADO", "02_POLIESTER", "03_LICRA_VELCRO"]
objs = [o for c in cols for o in bpy.data.collections[c].all_objects if o.type == 'MESH']
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for lc in bpy.context.view_layer.layer_collection.children:
    if lc.name in cols:
        lc.exclude = False
        lc.hide_viewport = False
for o in objs:
    o.hide_set(False)
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]

bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "dispositivo_textil.glb"), export_format='GLB',
                          use_selection=True, export_apply=True, export_yup=True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUT, "dispositivo_textil.obj"), export_selected_objects=True,
                      apply_modifiers=True, export_materials=True, forward_axis='NEGATIVE_Z', up_axis='Y')
bpy.ops.wm.stl_export(filepath=os.path.join(OUT, "dispositivo_textil.stl"), export_selected_objects=True,
                      apply_modifiers=True)
for f in sorted(os.listdir(OUT)):
    print("[EXPORT]", f, os.path.getsize(os.path.join(OUT, f)))
