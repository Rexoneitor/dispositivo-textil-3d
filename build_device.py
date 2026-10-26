# -*- coding: utf-8 -*-
"""
Dispositivo textil circular: neopreno perforado + lamina de poliester + licra con velcro medico.
Script reproducible para Blender (>= 4.2, probado en 5.2).

USO
  Dentro de Blender (Scripting > Run Script) o via MCP:  exec(compile(open(RUTA).read(), RUTA, "exec"),
                                                                {"__file__": RUTA, "__name__": "__main__"})
  Desde linea de comandos:  blender -b --python build_device.py

PARAMETROS
  Todos los valores de DEFAULTS pueden sobrescribirse editando las propiedades personalizadas del
  objeto vacio "CTRL_Parametros" (coleccion 09_CONTROLES_PARAMETRICOS) y volviendo a ejecutar el script.
  Unidades: metros. Las dimensiones iniciales son PROVISIONALES (los bocetos no tienen escala fiable).

Sistema de coordenadas: Z vertical, plano XY = plano del anillo, frente (cierre) hacia -Y (camara),
abertura del anillo hacia +Y.
"""
import bpy
import bmesh
import math
import os
import json
import random
import shutil
import time
import traceback
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()

DEFAULTS = {
    "out_dir": HERE,
    "blend_name": "producto_textil.blend",
    # --- A. Neopreno perforado
    "inner_diameter": 0.180,       # diametro interior aproximado (m)  PROVISIONAL
    "band_width": 0.046,           # anchura de la banda (m)
    "neo_thickness": 0.0045,       # espesor del neopreno (m)
    "gap_angle": 34.0,             # separacion angular entre extremos (grados)
    "end_pad_angle": 22.0,         # longitud angular del refuerzo de extremo
    "end_pad_gain": 0.9,           # engrosamiento relativo del refuerzo
    "neo_step_deg": 1.0,
    "neo_corner_r": 0.0012,
    "holes_rows": 4,
    "hole_diameter": 0.0060,
    "hole_pitch": 0.0125,          # paso entre perforaciones a lo largo del arco
    "hole_row_pitch": 0.0105,
    "hole_front_clear_deg": 58.0,  # zona frontal sin perforaciones (poliester + cierre)
    "hole_end_margin_deg": 6.0,    # margen respecto al refuerzo del extremo
    "hole_segments": 14,
    # --- B. Poliester (lamina en forma de "I")
    "poly_half_arc_deg": 52.0,
    "poly_bar_h": 0.0100,
    "poly_web_half_deg": 11.0,
    "poly_thickness": 0.0012,
    "poly_gap": 0.0004,
    "poly_inset": 0.0005,
    # --- C. Licra + velcro
    "lycra_half_arc_deg": 22.0,
    "lycra_body_z0": -0.0275,
    "lycra_body_z1": 0.0225,
    "lycra_thickness": 0.0016,
    "lycra_gap": 0.0004,
    "lycra_corner_r": 0.004,
    "flap_half_arc_deg": 14.0,
    "flap_z1": 0.0385,
    "flap_overlap": 0.004,
    "velcro_loop_w": 0.040,
    "velcro_loop_h": 0.0140,
    "velcro_loop_zc": -0.0040,
    "velcro_hook_w": 0.030,
    "velcro_hook_h": 0.0100,
    "velcro_hook_zc": 0.0305,
    "velcro_pitch": 0.00115,
    # --- Costuras / texturas
    "stitch_intensity": 1.0,
    "stitch_len": 0.0028,
    "stitch_pitch": 0.0042,
    "texture_scale": 1.0,
    # --- Colores (RGB lineal)
    "color_neoprene": (0.013, 0.013, 0.015),
    "color_polyester": (0.045, 0.075, 0.130),
    "color_lycra": (0.050, 0.052, 0.060),
    "color_loop": (0.62, 0.56, 0.45),
    "color_hook": (0.80, 0.80, 0.78),
    # --- Despiece
    "explode_dist": 0.095,
    "row_dist": 0.27,
    # --- Render
    "res_x": 1920,
    "res_y": 1080,
    "samples": 96,
    "denoise": True,
    "seed": 7,
}

COLS = [
    "00_REFERENCIAS", "01_NEOPRENO_PERFORADO", "02_POLIESTER", "03_LICRA_VELCRO", "04_ENSAMBLAJE",
    "05_MATERIALES", "06_CAMARAS", "07_ILUMINACION", "08_PRESENTACION_TECNICA", "09_CONTROLES_PARAMETRICOS",
]

LOG = []


def log(msg):
    LOG.append(msg)
    print("[BUILD] " + msg)


# ----------------------------------------------------------------------------- utilidades generales
def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def load_params():
    P = dict(DEFAULTS)
    ctrl = bpy.data.objects.get("CTRL_Parametros")
    if ctrl is not None:
        for k, v in DEFAULTS.items():
            if k == "out_dir":
                continue  # siempre la carpeta del script: el proyecto puede moverse
            if k in ctrl.keys():
                try:
                    val = ctrl[k]
                    if isinstance(v, tuple):
                        val = tuple(val)
                    elif isinstance(v, bool):
                        val = bool(val)
                    elif isinstance(v, int):
                        val = int(val)
                    elif isinstance(v, float):
                        val = float(val)
                    P[k] = val
                except Exception:
                    log("AVISO: no se pudo leer el parametro %s del control" % k)
    return P


def get_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    elif col.name not in [c.name for c in (parent or bpy.context.scene.collection).children]:
        try:
            (parent or bpy.context.scene.collection).children.link(col)
        except RuntimeError:
            pass
    return col


def clear_previous():
    """Elimina solo lo creado por este script (colecciones propias y los objetos por defecto)."""
    for nm in ("Cube", "Camera", "Light"):
        o = bpy.data.objects.get(nm)
        if o is not None and o.users_collection and o.users_collection[0].name == "Collection":
            bpy.data.objects.remove(o, do_unlink=True)
    ctrl = bpy.data.objects.get("CTRL_Parametros")
    for cn in COLS:
        col = bpy.data.collections.get(cn)
        if col is None:
            continue
        for o in list(col.all_objects):
            dname = o.data.name if o.data is not None else None
            dtype = o.type
            bpy.data.objects.remove(o, do_unlink=True)
            if dname:
                coll = {"MESH": bpy.data.meshes, "FONT": bpy.data.curves, "CAMERA": bpy.data.cameras,
                        "LIGHT": bpy.data.lights}.get(dtype)
                if coll is not None and dname in coll and coll[dname].users == 0:
                    coll.remove(coll[dname])
        bpy.data.collections.remove(col)
    del ctrl


def link_obj(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def mesh_object(name, bm, col, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    me.update()
    obj = bpy.data.objects.new(name, me)
    col.objects.link(obj)
    return obj


def cyl_point(r, phi_rad, z):
    th = -math.pi / 2 + phi_rad
    return Vector((r * math.cos(th), r * math.sin(th), z))


def frame_at(phi_rad):
    th = -math.pi / 2 + phi_rad
    n = Vector((math.cos(th), math.sin(th), 0.0))
    t = Vector((-math.sin(th), math.cos(th), 0.0))
    return n, t


def add_smooth_by_angle(obj, angle_deg=35.0):
    """Modifier 'Smooth by Angle' (activo esencial) con alternativa WeightedNormal."""
    try:
        ng = bpy.data.node_groups.get("Smooth by Angle")
        if ng is None:
            lib = os.path.join(bpy.utils.system_resource('DATAFILES'), "assets", "nodes",
                               "geometry_nodes_essentials.blend")
            with bpy.data.libraries.load(lib, link=False) as (src, dst):
                dst.node_groups = ["Smooth by Angle"]
            ng = bpy.data.node_groups.get("Smooth by Angle")
        if ng is None:
            raise RuntimeError("grupo de nodos no encontrado")
        mod = obj.modifiers.new("Suavizado_por_angulo", 'NODES')
        mod.node_group = ng
        try:
            for item in mod.node_group.interface.items_tree:
                if getattr(item, "in_out", "") == 'INPUT' and item.name == "Angle":
                    mod[item.identifier] = math.radians(angle_deg)
        except Exception as ex:
            log("AVISO: angulo del suavizado queda en su valor por defecto (30 grados): %s" % ex)
        return True
    except Exception as ex:
        log("AVISO: 'Smooth by Angle' no disponible (%s); se usa WeightedNormal" % ex)
        try:
            for p in obj.data.polygons:
                p.use_smooth = True
            m = obj.modifiers.new("Normales_ponderadas", 'WEIGHTED_NORMAL')
            m.keep_sharp = True
        except Exception as ex2:
            log("AVISO: alternativa de suavizado fallo: %s" % ex2)
        return False


# ----------------------------------------------------------------------------- mallas por rejilla enmascarada
def masked_shell(name, col, r, phi_half_deg, z0, z1, mask, step_deg=0.5, dz=0.000625):
    """Lamina curva sobre un cilindro de radio r. Solo se generan las celdas donde mask(u,z)=True.
    u = longitud de arco desde el frente (m). Devuelve el objeto."""
    nphi = int(round(2 * phi_half_deg / step_deg))
    nz = int(round((z1 - z0) / dz))
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    verts = {}
    step = math.radians(step_deg)

    def vtx(i, j):
        k = (i, j)
        if k not in verts:
            phi = math.radians(-phi_half_deg) + i * step
            verts[k] = (bm.verts.new(cyl_point(r, phi, z0 + j * dz)), phi * r, z0 + j * dz)
        return verts[k]

    for i in range(nphi):
        uc = (math.radians(-phi_half_deg) + (i + 0.5) * step) * r
        for j in range(nz):
            zc = z0 + (j + 0.5) * dz
            if not mask(uc, zc):
                continue
            q = [vtx(i, j), vtx(i + 1, j), vtx(i + 1, j + 1), vtx(i, j + 1)]
            f = bm.faces.new([a[0] for a in q])
            for lp, a in zip(f.loops, q):
                lp[uv].uv = (a[1], a[2])
    bm.normal_update()
    return mesh_object(name, bm, col)


def rr_mask(uc, zc, hw, hh, rc):
    """Mascara de rectangulo redondeado centrado en (uc, zc)."""
    def f(u, z):
        du, dz_ = abs(u - uc), abs(z - zc)
        if du > hw or dz_ > hh:
            return False
        if du > hw - rc and dz_ > hh - rc:
            return math.hypot(du - (hw - rc), dz_ - (hh - rc)) <= rc
        return True
    return f


def add_solidify_bevel(obj, thickness, bevel=0.00025, offset=1.0):
    s = obj.modifiers.new("Espesor", 'SOLIDIFY')
    s.thickness = thickness
    s.offset = offset
    s.use_even_offset = True
    b = obj.modifiers.new("Bisel_bordes", 'BEVEL')
    b.width = bevel
    b.segments = 2
    b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(40)
    return s


def rr_poly(uc, zc, hw, hh, rc, n=6, pts_per_m=2000):
    """Polilinea cerrada de un rectangulo redondeado (u, z)."""
    pts = []
    corners = [(uc + hw - rc, zc + hh - rc, 0), (uc - hw + rc, zc + hh - rc, 90),
               (uc - hw + rc, zc - hh + rc, 180), (uc + hw - rc, zc - hh + rc, 270)]
    for cx, cz, a0 in corners:
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((cx + rc * math.cos(a), cz + rc * math.sin(a)))
    pts.append(pts[0])
    return pts


def stitches(name, col, polylines, r, P, mat=None):
    """Costura discreta: elipsoides aplanados distribuidos a paso constante sobre polilineas (u, z)."""
    bm = bmesh.new()
    I = P["stitch_intensity"]
    ls, ws, hs = P["stitch_len"], 0.00055 * I, 0.00032 * I
    pitch = P["stitch_pitch"]
    for poly in polylines:
        carry = 0.0
        for (u0, z0), (u1, z1) in zip(poly[:-1], poly[1:]):
            seg = math.hypot(u1 - u0, z1 - z0)
            if seg < 1e-9:
                continue
            d = ((u1 - u0) / seg, (z1 - z0) / seg)
            s = carry
            while s < seg:
                u, z = u0 + d[0] * s, z0 + d[1] * s
                n, t = frame_at(u / r)
                T = t * d[0] + Vector((0, 0, 1)) * d[1]
                T.normalize()
                B = n.cross(T)
                B.normalize()
                rot = Matrix((T, B, n)).transposed().to_4x4()
                center = cyl_point(r, u / r, z) + n * (hs * 0.35)
                M = Matrix.Translation(center) @ rot @ Matrix.Diagonal((ls, ws, hs, 1.0))
                bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=4, radius=0.5, matrix=M)
                s += pitch
            carry = s - seg
    obj = mesh_object(name, bm, col)
    if mat:
        obj.data.materials.append(mat)
    return obj


# ----------------------------------------------------------------------------- COMPONENTE A: neopreno
def hole_layout(P):
    Rin = P["inner_diameter"] / 2
    Rm = Rin + P["neo_thickness"] / 2
    phimax = 180.0 - P["gap_angle"] / 2
    phi_lim = phimax - P["end_pad_angle"] - P["hole_end_margin_deg"]
    step_deg = math.degrees(P["hole_pitch"] / Rm)
    rows = int(P["holes_rows"])
    out = []
    for j in range(rows):
        zj = (j - (rows - 1) / 2.0) * P["hole_row_pitch"]
        off = 0.5 if (j % 2) else 0.0
        k = 0
        while True:
            a = P["hole_front_clear_deg"] + (k + off) * step_deg
            if a > phi_lim:
                break
            for sgn in (1, -1):
                out.append((sgn * a, zj))
            k += 1
    return out, Rm


def build_neoprene(P, col, mats):
    Rin = P["inner_diameter"] / 2
    t = P["neo_thickness"]
    hw = P["band_width"] / 2
    rc = P["neo_corner_r"]
    phimax = 180.0 - P["gap_angle"] / 2
    step = P["neo_step_deg"]
    n = int(round(2 * phimax / step))
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    rings = []
    for i in range(n + 1):
        phi_d = -phimax + i * (2 * phimax / n)
        e = phimax - abs(phi_d)
        s = 1.0 - smoothstep(e / P["end_pad_angle"]) if e < P["end_pad_angle"] else 0.0
        Ro = Rin + t * (1.0 + P["end_pad_gain"] * s)
        prof = []
        for (cr, cz, a0) in ((Ro - rc, hw - rc, 0), (Rin + rc, hw - rc, 90),
                             (Rin + rc, -hw + rc, 180), (Ro - rc, -hw + rc, 270)):
            for k in range(4):
                a = math.radians(a0 + 90.0 * k / 3.0)
                prof.append((cr + rc * math.cos(a), cz + rc * math.sin(a)))
        phi = math.radians(phi_d)
        ring = [bm.verts.new(cyl_point(rr, phi, zz)) for rr, zz in prof]
        rings.append((ring, phi * (Rin + t / 2), [zz for _, zz in prof]))
    m = len(rings[0][0])
    for i in range(n):
        for k in range(m):
            k2 = (k + 1) % m
            f = bm.faces.new([rings[i][0][k], rings[i][0][k2], rings[i + 1][0][k2], rings[i + 1][0][k]])
            for lp in f.loops:
                idx = [(ii, kk) for ii in (i, i + 1) for kk in range(m) if rings[ii][0][kk] == lp.vert][0]
                lp[uv].uv = (rings[idx[0]][1], rings[idx[0]][2][idx[1]])
    for ring_i, rev in ((0, True), (n, False)):
        vs = list(rings[ring_i][0])
        if rev:
            vs.reverse()
        f = bm.faces.new(vs)
        for lp in f.loops:
            kk = rings[ring_i][0].index(lp.vert)
            lp[uv].uv = (rings[ring_i][1], rings[ring_i][2][kk])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = mesh_object("A_Neopreno_Banda", bm, col)
    obj.data.materials.append(mats["neoprene"])

    # perforaciones: cortadores cilindricos radiales (geometria real)
    holes, Rm = hole_layout(P)
    cb = bmesh.new()
    rh = P["hole_diameter"] / 2
    ch = min(0.0005, rh * 0.25)   # chaflan de borde de cada perforacion
    prof = [(-t / 2 - 0.001, rh + ch + 0.001), (-t / 2, rh + ch), (-t / 2 + ch, rh),
            (t / 2 - ch, rh), (t / 2, rh + ch), (t / 2 + 0.001, rh + ch + 0.001)]
    nseg = int(P["hole_segments"])
    for phi_d, zj in holes:
        nrm, tan = frame_at(math.radians(phi_d))
        zax = Vector((0, 0, 1))
        c0 = cyl_point(Rm, math.radians(phi_d), zj)
        rings_h = []
        for d, rad in prof:
            rings_h.append([cb.verts.new(c0 + nrm * d + (tan * math.cos(2 * math.pi * s / nseg) +
                                                         zax * math.sin(2 * math.pi * s / nseg)) * rad)
                            for s in range(nseg)])
        for k in range(len(prof) - 1):
            for s in range(nseg):
                s2 = (s + 1) % nseg
                cb.faces.new([rings_h[k][s], rings_h[k][s2], rings_h[k + 1][s2], rings_h[k + 1][s]])
        cb.faces.new(rings_h[0][::-1])
        cb.faces.new(rings_h[-1])
    bmesh.ops.recalc_face_normals(cb, faces=cb.faces)
    cutter = mesh_object("A_Cortadores_Perforaciones", cb, get_collection("09_CONTROLES_PARAMETRICOS"), smooth=False)
    cutter.display_type = 'WIRE'
    cutter.hide_render = True
    cutter.hide_set(True)

    bo = obj.modifiers.new("Perforaciones_booleanas", 'BOOLEAN')
    bo.operation = 'DIFFERENCE'
    bo.object = cutter
    bo.solver = 'EXACT'
    for p in obj.data.polygons:
        p.use_smooth = True
    add_smooth_by_angle(obj, 40.0)
    obj["n_perforaciones"] = len(holes)
    log("Neopreno: %d perforaciones" % len(holes))
    return obj, len(holes)


# ----------------------------------------------------------------------------- COMPONENTE B: poliester
def radii(P):
    Ro = P["inner_diameter"] / 2 + P["neo_thickness"]
    r_poly = Ro + P["poly_gap"]
    r_body = r_poly + P["poly_thickness"] + P["lycra_gap"]
    r_flap = r_body + P["lycra_thickness"] + P["lycra_gap"] * 0.75
    return Ro, r_poly, r_body, r_flap


def build_polyester(P, col, mats):
    _, r, _, _ = radii(P)
    hh = P["band_width"] / 2 - P["poly_inset"]
    bh = P["poly_bar_h"]
    Sb = math.radians(P["poly_half_arc_deg"]) * r
    Sw = math.radians(P["poly_web_half_deg"]) * r

    def mask(u, z):
        return (abs(z) > hh - bh) or (abs(u) < Sw)

    obj = masked_shell("B_Poliester_Lamina", col, r, P["poly_half_arc_deg"], -hh, hh, mask)
    add_solidify_bevel(obj, P["poly_thickness"], 0.00020)
    obj.data.materials.append(mats["polyester"])
    # costuras
    ins = 0.0016
    polys = [rr_poly(0, hh - bh / 2, Sb - ins, bh / 2 - ins, 0.0012),
             rr_poly(0, -hh + bh / 2, Sb - ins, bh / 2 - ins, 0.0012),
             rr_poly(0, 0, Sw - ins, hh - bh - 0.0010, 0.0012)]
    st = stitches("B_Poliester_Costuras", col, polys, r + P["poly_thickness"], P, mats["thread_poly"])
    st.parent = obj
    return obj, st


# ----------------------------------------------------------------------------- COMPONENTE C: licra + velcro
def hooks_patch(P, col, r_base, uc, zc, w, h, mats, rng):
    bm = bmesh.new()
    pitch = P["velcro_pitch"]
    nu, nz = int(w / pitch), int(h / pitch)
    for a in range(nu):
        for b in range(nz):
            u = uc - w / 2 + (a + 0.5) * pitch + rng.uniform(-0.00008, 0.00008)
            z = zc - h / 2 + (b + 0.5) * pitch + rng.uniform(-0.00008, 0.00008)
            n, t = frame_at(u / r_base)
            rot = n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
            base = cyl_point(r_base, u / r_base, z)
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=6, radius1=0.00017, radius2=0.00014,
                                  depth=0.0007, matrix=Matrix.Translation(base + n * 0.00035) @ rot)
            lean = t * rng.uniform(-0.00006, 0.00006)
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8, radius1=0.00042, radius2=0.00016,
                                  depth=0.00028, matrix=Matrix.Translation(base + n * 0.00084 + lean) @ rot)
    obj = mesh_object("C_Velcro_Ganchos", bm, col)
    obj.data.materials.append(mats["hook"])
    return obj


def loops_patch(P, col, r_base, uc, zc, w, h, mats, rng):
    bm = bmesh.new()
    pitch = P["velcro_pitch"]
    nu, nz = int(w / pitch), int(h / pitch)
    npts = 7
    for a in range(nu):
        for b in range(nz):
            for _ in range(2):
                u = uc - w / 2 + (a + rng.random()) * pitch
                z = zc - h / 2 + (b + rng.random()) * pitch
                n, t = frame_at(u / r_base)
                ang = rng.uniform(0, math.pi)
                T = (t * math.cos(ang) + Vector((0, 0, 1)) * math.sin(ang))
                B = n.cross(T)
                hw_ = rng.uniform(0.00032, 0.00055)
                hh_ = rng.uniform(0.00040, 0.00075)
                c = cyl_point(r_base, u / r_base, z)
                path = []
                for k in range(npts):
                    al = math.pi - math.pi * k / (npts - 1)
                    path.append(c + T * (math.cos(al) * hw_) + n * (math.sin(al) * hh_))
                rings = []
                for k, p in enumerate(path):
                    d = (path[min(k + 1, npts - 1)] - path[max(k - 1, 0)]).normalized()
                    u2 = d.cross(B).normalized()
                    rw = 0.000055
                    rings.append([bm.verts.new(p + B * rw), bm.verts.new(p + u2 * rw),
                                  bm.verts.new(p - B * rw), bm.verts.new(p - u2 * rw)])
                for k in range(npts - 1):
                    for q in range(4):
                        q2 = (q + 1) % 4
                        bm.faces.new([rings[k][q], rings[k][q2], rings[k + 1][q2], rings[k + 1][q]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = mesh_object("C_Velcro_Bucles", bm, col)
    obj.data.materials.append(mats["loop"])
    return obj


def backing(name, col, r, uc, zc, w, h, mat, thickness=0.00035):
    sx = math.degrees((w / 2) / r)
    obj = masked_shell(name, col, r, sx, zc - h / 2, zc + h / 2, rr_mask(0, zc, w / 2, h / 2, 0.0015),
                       step_deg=0.5, dz=0.000625)
    add_solidify_bevel(obj, thickness, 0.00012)
    obj.data.materials.append(mat)
    return obj


def build_lycra(P, col, mats):
    _, _, r_body, r_flap = radii(P)
    lt = P["lycra_thickness"]
    rng = random.Random(int(P["seed"]))
    z0, z1 = P["lycra_body_z0"], P["lycra_body_z1"]
    hwb = math.radians(P["lycra_half_arc_deg"]) * r_body
    body = masked_shell("C_Licra_Cuerpo", col, r_body, P["lycra_half_arc_deg"], z0, z1,
                        rr_mask(0, (z0 + z1) / 2, hwb, (z1 - z0) / 2, P["lycra_corner_r"]))
    add_solidify_bevel(body, lt, 0.00030)
    body.data.materials.append(mats["lycra"])

    fz0 = z1 - P["flap_overlap"]
    fz1 = P["flap_z1"]
    hwf = math.radians(P["flap_half_arc_deg"]) * r_flap
    flap = masked_shell("C_Licra_Solapa", col, r_flap, P["flap_half_arc_deg"], fz0, fz1,
                        rr_mask(0, (fz0 + fz1) / 2, hwf, (fz1 - fz0) / 2, P["lycra_corner_r"] * 0.8))
    add_solidify_bevel(flap, lt, 0.00030)
    flap.data.materials.append(mats["lycra"])

    # velcro: bucles en el cuerpo, ganchos en la solapa
    r_loop = r_body + lt + 0.00003
    r_hook = r_flap + lt + 0.00003
    loop_back = backing("C_Velcro_Base_Bucles", col, r_loop, 0, P["velcro_loop_zc"], P["velcro_loop_w"],
                        P["velcro_loop_h"], mats["loop_backing"])
    hook_back = backing("C_Velcro_Base_Ganchos", col, r_hook, 0, P["velcro_hook_zc"], P["velcro_hook_w"],
                        P["velcro_hook_h"], mats["hook_backing"])
    loops = loops_patch(P, col, r_loop + 0.00035, 0, P["velcro_loop_zc"], P["velcro_loop_w"] - 0.0015,
                        P["velcro_loop_h"] - 0.0015, mats, rng)
    hooks = hooks_patch(P, col, r_hook + 0.00035, 0, P["velcro_hook_zc"], P["velcro_hook_w"] - 0.0015,
                        P["velcro_hook_h"] - 0.0015, mats, rng)
    # costuras
    ins = 0.0018
    polys_b = [rr_poly(0, (z0 + z1) / 2, hwb - ins, (z1 - z0) / 2 - ins, P["lycra_corner_r"] - 0.001)]
    seam = [(-(hwf - 0.002), z1 - P["flap_overlap"] / 2), ((hwf - 0.002), z1 - P["flap_overlap"] / 2)]
    st_b = stitches("C_Licra_Costuras_Cuerpo", col, polys_b + [seam], r_body + lt, P, mats["thread_lycra"])
    polys_f = [rr_poly(0, (fz0 + fz1) / 2 + P["flap_overlap"] / 2, hwf - ins,
                       (fz1 - fz0 - P["flap_overlap"]) / 2 - ins, 0.003)]
    st_f = stitches("C_Licra_Costuras_Solapa", col, polys_f, r_flap + lt, P, mats["thread_lycra"])
    parts = [body, flap, loop_back, hook_back, loops, hooks, st_b, st_f]
    for o in parts[1:]:
        o.parent = body
    return body, parts


# ----------------------------------------------------------------------------- MATERIALES PBR
def _new_mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    return m, nt


def _n(nt, typ, loc, **kw):
    node = nt.nodes.new(typ)
    node.location = loc
    for k, v in kw.items():
        setattr(node, k, v)
    return node


def _principled(nt, color, rough, **extra):
    out = _n(nt, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(nt, "ShaderNodeBsdfPrincipled", (600, 0))
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    for k, v in extra.items():
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = v
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf


def _bump(nt, bsdf, height_socket, strength, dist, loc=(350, -250)):
    b = _n(nt, "ShaderNodeBump", loc)
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    nt.links.new(height_socket, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])


def _math(nt, op, a, b=None, loc=(0, 0), c=None):
    m = _n(nt, "ShaderNodeMath", loc, operation=op)
    for idx, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[idx].default_value = v
        else:
            nt.links.new(v, m.inputs[idx])
    return m.outputs[0]


def _weave(nt, uvvec, pitch_u, pitch_v, loc_x=-400):
    sep = _n(nt, "ShaderNodeSeparateXYZ", (loc_x, -300))
    nt.links.new(uvvec, sep.inputs[0])
    tp = 2 * math.pi
    su = _math(nt, 'MULTIPLY', sep.outputs[0], tp / pitch_u, loc=(loc_x + 150, -250))
    su = _math(nt, 'SINE', su, loc=(loc_x + 300, -250))
    su = _math(nt, 'MULTIPLY_ADD', su, 0.5, loc=(loc_x + 450, -250), c=0.5)
    sv = _math(nt, 'MULTIPLY', sep.outputs[1], tp / pitch_v, loc=(loc_x + 150, -400))
    sv = _math(nt, 'SINE', sv, loc=(loc_x + 300, -400))
    sv = _math(nt, 'MULTIPLY_ADD', sv, 0.5, loc=(loc_x + 450, -400), c=0.5)
    return _math(nt, 'MULTIPLY', su, sv, loc=(loc_x + 600, -320))


def _noise(nt, vec, scale, detail=6.0, rough=0.55, loc=(-300, 200)):
    nz = _n(nt, "ShaderNodeTexNoise", loc)
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    nz.inputs["Roughness"].default_value = rough
    nt.links.new(vec, nz.inputs["Vector"])
    return nz


def make_materials(P):
    ts = P["texture_scale"]
    mats = {}

    # A. Neopreno: espuma tecnica mate, microceldas
    m, nt = _new_mat("MAT_A_Neopreno_Perforado")
    tc = _n(nt, "ShaderNodeTexCoord", (-900, 0))
    mp = _n(nt, "ShaderNodeMapping", (-700, 0))
    mp.inputs["Scale"].default_value = (ts, ts, ts)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    bsdf = _principled(nt, P["color_neoprene"], 0.82, **{"Specular IOR Level": 0.25})
    n1 = _noise(nt, mp.outputs[0], 650.0, 8.0, 0.6)
    vo = _n(nt, "ShaderNodeTexVoronoi", (-500, -50))
    vo.inputs["Scale"].default_value = 380.0
    nt.links.new(mp.outputs[0], vo.inputs["Vector"])
    inv = _math(nt, 'SUBTRACT', 1.0, vo.outputs["Distance"], loc=(-250, -50))
    h = _math(nt, 'MULTIPLY_ADD', n1.outputs["Fac"], 0.55, loc=(-100, 100),
              c=_math(nt, 'MULTIPLY', inv, 0.45, loc=(-250, -150)))
    _bump(nt, bsdf, h, 0.55, 0.0007)
    ramp = _n(nt, "ShaderNodeValToRGB", (100, 250))
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.70, 0.70, 0.70, 1)
    ramp.color_ramp.elements[1].position = 0.65
    ramp.color_ramp.elements[1].color = (0.92, 0.92, 0.92, 1)
    nt.links.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Roughness"])
    mats["neoprene"] = m

    # B. Poliester: tejido compacto, trama fina
    m, nt = _new_mat("MAT_B_Poliester_Tejido")
    tc = _n(nt, "ShaderNodeTexCoord", (-900, 0))
    bsdf = _principled(nt, P["color_polyester"], 0.50,
                       **{"Specular IOR Level": 0.45, "Sheen Weight": 0.08, "Sheen Roughness": 0.5})
    wv = _weave(nt, tc.outputs["UV"], 0.00085 / ts, 0.00085 / ts)
    nz = _noise(nt, tc.outputs["UV"], 1800.0 * ts, 3.0, 0.5)
    hh = _math(nt, 'MULTIPLY_ADD', nz.outputs["Fac"], 0.25, loc=(150, -250),
               c=_math(nt, 'MULTIPLY', wv, 0.9, loc=(0, -350)))
    _bump(nt, bsdf, hh, 0.45, 0.0004)
    mats["polyester"] = m

    # C. Licra: punto elastico fino, brillo satinado suave
    m, nt = _new_mat("MAT_C_Licra_Elastica")
    tc = _n(nt, "ShaderNodeTexCoord", (-900, 0))
    bsdf = _principled(nt, P["color_lycra"], 0.50,
                       **{"Specular IOR Level": 0.35, "Sheen Weight": 0.10, "Sheen Roughness": 0.4})
    wv = _weave(nt, tc.outputs["UV"], 0.00045 / ts, 0.00065 / ts)
    nz = _noise(nt, tc.outputs["UV"], 2600.0 * ts, 2.0, 0.5)
    hh = _math(nt, 'MULTIPLY_ADD', nz.outputs["Fac"], 0.15, loc=(150, -250),
               c=_math(nt, 'MULTIPLY', wv, 0.7, loc=(0, -350)))
    _bump(nt, bsdf, hh, 0.30, 0.0003)
    mats["lycra"] = m

    # D. Velcro: ganchos (nylon rigido), bucles (fibra suave), bases tejidas
    m, nt = _new_mat("MAT_D_Velcro_Ganchos")
    _principled(nt, P["color_hook"], 0.38, **{"Specular IOR Level": 0.5})
    mats["hook"] = m

    m, nt = _new_mat("MAT_D_Velcro_Bucles")
    _principled(nt, P["color_loop"], 0.88, **{"Sheen Weight": 0.5, "Sheen Roughness": 0.5})
    mats["loop"] = m

    m, nt = _new_mat("MAT_D_Velcro_Base_Bucles")
    tc = _n(nt, "ShaderNodeTexCoord", (-900, 0))
    c = tuple(x * 0.55 for x in P["color_loop"])
    bsdf = _principled(nt, c, 0.9)
    nz = _noise(nt, tc.outputs["UV"], 3000.0 * ts, 5.0, 0.6)
    _bump(nt, bsdf, nz.outputs["Fac"], 0.6, 0.0005)
    mats["loop_backing"] = m

    m, nt = _new_mat("MAT_D_Velcro_Base_Ganchos")
    tc = _n(nt, "ShaderNodeTexCoord", (-900, 0))
    bsdf = _principled(nt, (0.30, 0.30, 0.30), 0.6)
    wv = _weave(nt, tc.outputs["UV"], 0.0007 / ts, 0.0007 / ts)
    _bump(nt, bsdf, wv, 0.3, 0.0002)
    mats["hook_backing"] = m

    for key, nm, base in (("thread_poly", "MAT_Hilo_Poliester", (0.14, 0.20, 0.32)),
                          ("thread_lycra", "MAT_Hilo_Licra", (0.30, 0.31, 0.34))):
        m, nt = _new_mat(nm)
        _principled(nt, base, 0.55, **{"Sheen Weight": 0.3})
        mats[key] = m

    m, nt = _new_mat("MAT_Estudio_Suelo")
    _principled(nt, (0.40, 0.395, 0.39), 0.55)
    mats["floor"] = m

    m, nt = _new_mat("MAT_Etiqueta")
    _principled(nt, (0.015, 0.015, 0.018), 0.6)
    mats["label"] = m

    m, nt = _new_mat("MAT_Guia_Despiece")
    _principled(nt, (0.9, 0.35, 0.05), 0.5)
    mats["guide"] = m
    return mats


# ----------------------------------------------------------------------------- escena: estudio, luces, camaras
def build_studio(P, mats, col_light, col_cam, col_tech):
    scene = bpy.context.scene
    zf = -0.0300
    prof = [(-3.0, zf), (0.45, zf)]
    R = 0.55
    for k in range(1, 13):
        a = math.radians(90.0 * k / 12)
        prof.append((0.45 + R * math.sin(a), zf + R * (1 - math.cos(a))))
    prof.append((0.45 + R, zf + 3.0))
    bm = bmesh.new()
    W = 6.0
    ra = [bm.verts.new((-W / 2, y, z)) for y, z in prof]
    rb = [bm.verts.new((W / 2, y, z)) for y, z in prof]
    for i in range(len(prof) - 1):
        bm.faces.new([ra[i], rb[i], rb[i + 1], ra[i + 1]])
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    floor = mesh_object("Estudio_Ciclorama", bm, col_light)
    floor.data.materials.append(mats["floor"])

    world = bpy.data.worlds.get("Mundo_Estudio") or bpy.data.worlds.new("Mundo_Estudio")
    try:
        world.use_nodes = True
    except Exception:
        pass
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.62, 0.61, 0.60, 1)
    bg.inputs["Strength"].default_value = 0.30
    nt.links.new(bg.outputs[0], out.inputs[0])
    scene.world = world

    tgt = bpy.data.objects.new("LUZ_Objetivo", None)
    tgt.empty_display_type = 'PLAIN_AXES'
    tgt.empty_display_size = 0.02
    tgt.location = (0, -0.03, 0.0)
    col_light.objects.link(tgt)

    def area(name, loc, size, power, color=(1, 1, 1), shape='RECTANGLE', size_y=None):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = power
        ld.shape = shape
        ld.size = size
        if size_y:
            ld.size_y = size_y
        ld.color = color
        o = bpy.data.objects.new(name, ld)
        o.location = loc
        col_light.objects.link(o)
        c = o.constraints.new('TRACK_TO')
        c.target = tgt
        c.track_axis = 'TRACK_NEGATIVE_Z'
        c.up_axis = 'UP_Y'
        return o

    area("LUZ_Principal_Softbox", (0.60, -0.70, 0.70), 0.9, 38, (1.0, 0.97, 0.93), size_y=0.6)
    area("LUZ_Relleno", (-0.80, -0.45, 0.30), 1.0, 12, (0.93, 0.96, 1.0))
    area("LUZ_Contraluz", (-0.25, 0.80, 0.55), 0.7, 30, (1, 1, 1), size_y=0.3)
    area("LUZ_Cenital_Suave", (0.0, -0.05, 1.0), 1.3, 10, (1, 1, 1), shape='SQUARE')

    cams = {}

    def cam(name, loc, target, lens, dof=None, rot=None):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.sensor_width = 36
        cd.clip_start = 0.01
        cd.clip_end = 20
        o = bpy.data.objects.new(name, cd)
        o.location = loc
        col_cam.objects.link(o)
        if rot is not None:
            o.rotation_euler = rot
        else:
            te = bpy.data.objects.new("OBJ_" + name, None)
            te.empty_display_type = 'SPHERE'
            te.empty_display_size = 0.004
            te.location = target
            col_cam.objects.link(te)
            c = o.constraints.new('TRACK_TO')
            c.target = te
            c.track_axis = 'TRACK_NEGATIVE_Z'
            c.up_axis = 'UP_Y'
            if dof:
                cd.dof.use_dof = True
                cd.dof.focus_object = te
                cd.dof.aperture_fstop = dof
        cams[name] = o
        return o

    cam("Cam_3Q_Principal", (0.44, -0.52, 0.31), (0, -0.035, 0.0), 75)
    cam("Cam_Frontal", (0, -0.80, 0.015), (0, 0, 0.0), 85)
    cam("Cam_Superior", (0, 0.0, 0.85), None, 85, rot=(0, 0, 0))
    cam("Cam_Lateral", (0.80, 0.0, 0.015), (0, 0, 0.0), 85)
    cam("Cam_Interior", (-0.055, -0.005, 0.125), (0.09, 0.0, -0.004), 45)
    cam("Cam_Detalle_Perforaciones", (0.255, -0.115, 0.075), (0.093, 0.006, 0.0), 100, dof=8.0)
    cam("Cam_Detalle_Cierre", (0.075, -0.265, 0.105), (0.0, -0.098, 0.013), 100, dof=11.0)
    cam("Cam_Despiece_Vertical", (0.42, -1.10, 0.30), (0.06, -0.02, 0.085), 62)
    cam("Cam_Despiece_Fila", (-0.05, -1.00, 0.03), (-0.05, 0.0, 0.02), 50)
    scene.camera = cams["Cam_3Q_Principal"]
    return cams, floor


def build_labels_guides(P, mats, col_tech):
    labels = {}
    texts = {"A": "A. Neopreno perforado", "B": "B. Cinta / lamina de poliester", "C": "C. Licra con velcro medico"}
    for k, txt in texts.items():
        cu = bpy.data.curves.new("TXT_" + k, 'FONT')
        cu.body = txt
        cu.size = 0.0105
        cu.align_x = 'LEFT'
        cu.extrude = 0.0002
        o = bpy.data.objects.new("ETIQUETA_" + k, cu)
        o.rotation_euler = (math.pi / 2, 0, 0)
        o.data.materials.append(mats["label"])
        col_tech.objects.link(o)
        labels[k] = o
    bm = bmesh.new()
    L = 2 * P["explode_dist"] + 0.07
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.00035, radius2=0.00035, depth=L,
                          matrix=Matrix.Translation((0, 0, L / 2 - 0.03)))
    g = mesh_object("GUIA_Despiece", bm, col_tech, smooth=False)
    g.data.materials.append(mats["guide"])
    g.location = (0, -(P["inner_diameter"] / 2 + P["neo_thickness"] + 0.0105), 0)
    g.hide_render = True
    return labels, g


STATE_NAMES = ("ensamblado", "despiece_vertical", "despiece_fila")


def set_state(name):
    """Coloca los tres componentes: ensamblado, despiece vertical o despiece en fila (sin rotar)."""
    P = load_params()
    A = bpy.data.objects["ASM_Neopreno"]
    B = bpy.data.objects["ASM_Poliester"]
    C = bpy.data.objects["ASM_LicraVelcro"]
    lab = {k: bpy.data.objects.get("ETIQUETA_" + k) for k in "ABC"}
    guide = bpy.data.objects.get("GUIA_Despiece")
    Rf = P["inner_diameter"] / 2 + P["neo_thickness"]
    d = P["explode_dist"]
    for o in (A, B, C):
        o.location = (0, 0, 0)
    for o in lab.values():
        if o:
            o.hide_render = True
            o.hide_viewport = True
    if guide:
        guide.hide_render = True
        guide.hide_viewport = True
    if name == "despiece_vertical":
        B.location = (0, 0, d)
        C.location = (0, 0, 2 * d)
        for k, z in (("A", 0.0), ("B", d), ("C", 2 * d)):
            lab[k].location = (0.125, -Rf - 0.02, z - 0.004)
            lab[k].data.align_x = 'LEFT'
        if guide:
            guide.hide_render = False
            guide.hide_viewport = False
    elif name == "despiece_fila":
        rd = P["row_dist"]
        A.location = (-rd, 0, 0)
        B.location = (0.0, Rf + 0.0105, 0)
        C.location = (rd * 0.78, Rf + 0.0105, 0)
        lab["A"].location = (-rd, -Rf - 0.02, 0.054)
        lab["B"].location = (0.0, -0.02, 0.054)
        lab["C"].location = (rd * 0.78, -0.02, 0.054)
        for o in lab.values():
            o.data.align_x = 'CENTER'
    if name != "ensamblado":
        for o in lab.values():
            o.hide_render = False
            o.hide_viewport = False
    bpy.context.view_layer.update()


def setup_viewport():
    """Deja el archivo listo para abrirse: vista de camara principal, materiales e iluminacion de la escena,
    sin ayudas visuales (camaras, luces, vacios) y con las colecciones auxiliares ocultas."""
    sc = bpy.context.scene
    sc.frame_current = 1
    sc.camera = bpy.data.objects.get("Cam_3Q_Principal") or sc.camera
    for lc in bpy.context.view_layer.layer_collection.children:
        if lc.name in ("00_REFERENCIAS", "05_MATERIALES", "09_CONTROLES_PARAMETRICOS"):
            lc.hide_viewport = True
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    asm = bpy.data.objects.get("ASM_Conjunto")
    if asm:
        bpy.context.view_layer.objects.active = asm
    try:
        sc.eevee.use_shadows = True
    except Exception:
        pass
    # color de visualizacion (vista Solid) = color base de cada material
    for m in bpy.data.materials:
        nt = getattr(m, "node_tree", None)
        bsdf = next((nd for nd in nt.nodes if nd.type == 'BSDF_PRINCIPLED'), None) if nt else None
        if bsdf is not None:
            c = bsdf.inputs["Base Color"].default_value
            m.diffuse_color = (c[0] ** 0.7, c[1] ** 0.7, c[2] ** 0.7, 1.0)
            m.roughness = bsdf.inputs["Roughness"].default_value
            m.metallic = 0.0
    n = 0
    for scr in bpy.data.screens:
        if scr.name != "Layout":
            continue
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            sp = area.spaces.active
            # SOLID (Workbench): estable en GPU integradas. EEVEE (Material Preview) provoca un cierre
            # en este equipo (eevee::LightModule); el aspecto fotorrealista se obtiene con F12 (Cycles).
            sp.shading.type = 'SOLID'
            sp.shading.light = 'STUDIO'
            sp.shading.color_type = 'MATERIAL'
            sp.shading.show_shadows = True
            sp.shading.shadow_intensity = 0.35
            sp.shading.show_cavity = True
            sp.shading.cavity_type = 'BOTH'
            sp.shading.show_specular_highlight = True
            sp.shading.background_type = 'VIEWPORT'
            sp.shading.background_color = (0.60, 0.60, 0.59)
            sp.clip_start = 0.001
            sp.clip_end = 50.0
            sp.lens = 50
            sp.overlay.show_extras = False
            sp.overlay.show_relationship_lines = False
            sp.overlay.show_floor = False
            sp.overlay.show_axis_x = False
            sp.overlay.show_axis_y = False
            sp.overlay.show_cursor = False
            sp.overlay.show_outline_selected = False
            sp.camera = sc.camera
            sp.region_3d.view_perspective = 'CAMERA'
            sp.region_3d.view_camera_zoom = 22.0
            sp.region_3d.view_camera_offset = (0.0, 0.0)
            n += 1
    log("Vistas 3D configuradas en camara principal: %d" % n)


def setup_render(P):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = int(P["samples"])
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = bool(P["denoise"])
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 8
    sc.cycles.preview_samples = 32
    sc.render.resolution_x = int(P["res_x"])
    sc.render.resolution_y = int(P["res_y"])
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'None'
    except Exception as ex:
        log("AVISO: view transform: %s" % ex)
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = 'MILLIMETERS'


# ----------------------------------------------------------------------------- referencias y controles
def build_references(P, col):
    ref_dir = os.path.join(P["out_dir"], "referencias")
    files = [f for f in sorted(os.listdir(ref_dir))] if os.path.isdir(ref_dir) else []
    for i, f in enumerate(files):
        try:
            img = bpy.data.images.load(os.path.join(ref_dir, f), check_existing=True)
            img.pack()
            e = bpy.data.objects.new("REF_boceto_%d" % (i + 1), None)
            e.empty_display_type = 'IMAGE'
            e.data = img
            e.empty_display_size = 0.32
            e.location = (-0.75 + 0.36 * i, 0.55, 0.12)
            e.rotation_euler = (math.pi / 2, 0, 0)
            e.hide_render = True
            col.objects.link(e)
        except Exception as ex:
            log("AVISO: referencia %s no cargada: %s" % (f, ex))
    return len(files)


def build_swatches(mats, col):
    keys = [("neoprene", "A"), ("polyester", "B"), ("lycra", "C"), ("hook", "D1"), ("loop", "D2")]
    for i, (k, tag) in enumerate(keys):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.02)
        o = mesh_object("MUESTRA_" + tag + "_" + k, bm, col)
        o.location = (-0.55 + i * 0.055, 0.85, 0.0)
        o.data.materials.append(mats[k])
        o.hide_render = True


def build_controls(P, col):
    ctrl = bpy.data.objects.new("CTRL_Parametros", None)
    ctrl.empty_display_type = 'ARROWS'
    ctrl.empty_display_size = 0.03
    ctrl.location = (0.0, 0.62, 0.0)
    col.objects.link(ctrl)
    for k, v in P.items():
        try:
            ctrl[k] = list(v) if isinstance(v, tuple) else v
        except Exception:
            pass
    ctrl["_AYUDA"] = ("Edite estos valores (metros) y vuelva a ejecutar build_device.py para regenerar "
                      "perforaciones, cierre y demas piezas. Dimensiones PROVISIONALES.")
    return ctrl


# ----------------------------------------------------------------------------- control de calidad
def eval_bm(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ev.matrix_world)
    ev.to_mesh_clear()
    return bm


def run_qc(P, objs):
    ok, warn, manual = [], [], []
    A, B = objs["A"], objs["B"]
    C_parts = objs["C"]

    def chk(cond, good, bad):
        if cond:
            ok.append(good)
        else:
            warn.append(bad)

    cols = [c for c in COLS if c in bpy.data.collections]
    chk(len(cols) == len(COLS), "Las 10 colecciones de la arquitectura existen", "Faltan colecciones")
    chk(A.name in bpy.data.collections["01_NEOPRENO_PERFORADO"].objects and
        B.name in bpy.data.collections["02_POLIESTER"].objects and
        all(o.name in bpy.data.collections["03_LICRA_VELCRO"].objects for o in C_parts),
        "Los tres componentes estan en colecciones independientes", "Componentes mal repartidos entre colecciones")
    chk(all(len(o.data.materials) > 0 for o in [A, B] + C_parts), "Todos los objetos tienen material asignado",
        "Hay objetos sin material")

    bmA = eval_bm(A)
    treeA = BVHTree.FromBMesh(bmA)
    t = P["neo_thickness"]
    chk(abs(A.dimensions.z - P["band_width"]) < 1e-4, "Anchura de banda = %.1f mm" % (P["band_width"] * 1000),
        "La anchura medida no coincide con el parametro")
    ok.append("Espesor visible del neopreno: %.1f mm (refuerzo de extremos hasta %.1f mm)" % (
        t * 1000, t * (1 + P["end_pad_gain"]) * 1000))

    holes, Rm = hole_layout(P)
    through, blocked, control_hit = 0, 0, 0
    for phi_d, zj in holes:
        nrm, _ = frame_at(math.radians(phi_d))
        o = cyl_point(Rm + 0.012, math.radians(phi_d), zj)
        hit = treeA.ray_cast(o, -nrm, 0.012 + t + 0.006)
        if hit[0] is None:
            through += 1
        else:
            blocked += 1
        zc = zj + P["hole_row_pitch"] * 0.5
        if abs(zc) < P["band_width"] / 2 - 0.004:
            o2 = cyl_point(Rm + 0.012, math.radians(phi_d), zc)
            if treeA.ray_cast(o2, -nrm, 0.012 + t + 0.006)[0] is not None:
                control_hit += 1
    chk(blocked == 0 and through == len(holes),
        "%d/%d perforaciones atraviesan completamente la banda (rayo radial sin impacto)" % (through, len(holes)),
        "%d perforaciones NO atraviesan (rayo bloqueado)" % blocked)
    chk(control_hit > 0, "Rayos de control entre filas golpean material solido (la banda no esta vacia)",
        "Rayos de control no impactan: revisar geometria")

    nm = sum(1 for e in bmA.edges if not e.is_manifold)
    chk(nm == 0, "Neopreno: malla evaluada cerrada y manifold (0 aristas abiertas)",
        "Neopreno: %d aristas no manifold" % nm)
    deg = sum(1 for f in bmA.faces if f.calc_area() < 1e-12)
    chk(deg == 0, "Neopreno: sin caras degeneradas", "Neopreno: %d caras degeneradas" % deg)
    vol = sum(f.calc_area() * f.normal.dot(f.calc_center_median()) for f in bmA.faces) / 3.0
    chk(vol > 0, "Neopreno: normales coherentes hacia el exterior (volumen %.2f cm3)" % (vol * 1e6),
        "Neopreno: volumen negativo, normales invertidas")
    ok.append("Neopreno evaluado: %d vertices, %d caras" % (len(bmA.verts), len(bmA.faces)))

    bmB = eval_bm(B)
    treeB = BVHTree.FromBMesh(bmB)
    ov_AB = len(treeA.overlap(treeB))
    chk(ov_AB == 0, "Sin intersecciones neopreno / poliester", "%d pares de caras se intersecan A-B" % ov_AB)
    ov_AC, ov_BC = 0, 0
    for o in C_parts:
        bmC = eval_bm(o)
        tc = BVHTree.FromBMesh(bmC)
        ov_AC += len(treeA.overlap(tc))
        ov_BC += len(treeB.overlap(tc))
        bmC.free()
    chk(ov_AC == 0, "Sin intersecciones neopreno / licra-velcro", "%d pares A-C se intersecan" % ov_AC)
    chk(ov_BC == 0, "Sin intersecciones poliester / licra-velcro", "%d pares B-C se intersecan" % ov_BC)
    ok.append("Poliester: espesor real %.1f mm (solidify), %d caras evaluadas" % (
        P["poly_thickness"] * 1000, len(bmB.faces)))
    degB = sum(1 for f in bmB.faces if f.calc_area() < 1e-14)
    chk(degB == 0, "Poliester: sin caras degeneradas", "Poliester: %d caras degeneradas" % degB)
    bmA.free()
    bmB.free()

    need = ("Cam_3Q_Principal", "Cam_Frontal", "Cam_Superior", "Cam_Detalle_Cierre", "Cam_Detalle_Perforaciones",
            "Cam_Interior", "Cam_Lateral", "Cam_Despiece_Vertical", "Cam_Despiece_Fila")
    chk(all(c in bpy.data.objects for c in need), "Las 9 camaras de presentacion y tecnicas existen", "Faltan camaras")
    ok.append("Velcro: ~%d ganchos tipo seta y ~%d bucles con geometria real; bases con relieve procedural" % (
        objs["n_hooks"], objs["n_loops"]))
    warn.append("Interseccion comprobada en estado ENSAMBLADO; los contactos velcro-licra son por proximidad (0.03 mm)")
    manual += [
        "Dimensiones reales: los bocetos no tienen escala; todo valor es provisional.",
        "Funcion exacta de la lamina de poliester (interpretada como pieza en 'I' de refuerzo/guia sobre el frente).",
        "Posicion de ganchos y bucles (bucles en cuerpo, ganchos en solapa) y detalle del cierre: supuestos de diseno.",
        "Aspecto real de costuras, colores y texturas: validar contra muestras fisicas.",
        "El modelo NO es apto para fabricacion ni implica propiedades medicas, resistencia o certificacion.",
        "Renders: revisar visualmente las imagenes antes de aprobar (no hay verificacion estetica automatica).",
    ]
    return ok, warn, manual


def write_report(P, ok, warn, manual, path, extra_lines=()):
    L = ["# Informe de validacion tecnica", "",
         "Generado por build_device.py (%s). Dimensiones provisionales." % time.strftime("%Y-%m-%d %H:%M"), ""]
    L += ["## Comprobaciones superadas"] + ["- " + s for s in ok] + [""]
    L += ["## Advertencias"] + (["- " + s for s in warn] or ["- (ninguna)"]) + [""]
    L += ["## Requiere validacion manual"] + ["- " + s for s in manual] + [""]
    if extra_lines:
        L += ["## Notas de ejecucion"] + ["- " + s for s in extra_lines] + [""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


# ----------------------------------------------------------------------------- principal
def main():
    t0 = time.time()
    if bpy.app.version < (4, 2, 0):
        log("AVISO: version de Blender %s < 4.2; algunas funciones pueden fallar" % bpy.app.version_string)
    P = load_params()
    os.makedirs(P["out_dir"], exist_ok=True)
    os.makedirs(os.path.join(P["out_dir"], "renders"), exist_ok=True)
    clear_previous()
    col = {n: get_collection(n) for n in COLS}
    mats = make_materials(P)
    try:
        build_controls(P, col["09_CONTROLES_PARAMETRICOS"])
        build_references(P, col["00_REFERENCIAS"])
        A, n_holes = build_neoprene(P, col["01_NEOPRENO_PERFORADO"], mats)
        B, stB = build_polyester(P, col["02_POLIESTER"], mats)
        Cbody, Cparts = build_lycra(P, col["03_LICRA_VELCRO"], mats)
        n_hooks = int(P["velcro_hook_w"] / P["velcro_pitch"]) * int(P["velcro_hook_h"] / P["velcro_pitch"])
        n_loops = 2 * int(P["velcro_loop_w"] / P["velcro_pitch"]) * int(P["velcro_loop_h"] / P["velcro_pitch"])
        root = bpy.data.objects.new("ASM_Conjunto", None)
        col["04_ENSAMBLAJE"].objects.link(root)
        asm = {}
        for nm in ("ASM_Neopreno", "ASM_Poliester", "ASM_LicraVelcro"):
            e = bpy.data.objects.new(nm, None)
            e.empty_display_type = 'PLAIN_AXES'
            e.empty_display_size = 0.02
            e.parent = root
            col["04_ENSAMBLAJE"].objects.link(e)
            asm[nm] = e
        A.parent = asm["ASM_Neopreno"]
        B.parent = asm["ASM_Poliester"]
        Cbody.parent = asm["ASM_LicraVelcro"]
        build_swatches(mats, col["05_MATERIALES"])
        build_studio(P, mats, col["07_ILUMINACION"], col["06_CAMARAS"], col["08_PRESENTACION_TECNICA"])
        build_labels_guides(P, mats, col["08_PRESENTACION_TECNICA"])
        setup_render(P)
        set_state("ensamblado")
        objs = {"A": A, "B": B, "C": Cparts, "n_hooks": n_hooks, "n_loops": n_loops}
        ok, warn, manual = run_qc(P, objs)
        setup_viewport()
    except Exception:
        log("ERROR: " + traceback.format_exc())
        raise
    out_blend = os.path.join(P["out_dir"], P["blend_name"])
    try:
        bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=False)
        ok.append("Archivo .blend guardado: " + out_blend)
    except Exception as ex:
        warn.append("No se pudo guardar el .blend: %s" % ex)
    write_report(P, ok, warn, manual, os.path.join(P["out_dir"], "reporte_validacion.md"),
                 ["Tiempo de construccion: %.1f s" % (time.time() - t0)] + [l for l in LOG if "AVISO" in l])
    log("Terminado en %.1f s" % (time.time() - t0))
    return {"ok": ok, "warn": warn, "manual": manual}


if __name__ == "__main__":
    RESULT = main()
