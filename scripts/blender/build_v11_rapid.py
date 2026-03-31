"""
Sponic Garden — v11 AI-ASSIST STRUCTURAL
High-quality Cycles renders designed as depth/layout guides for Gemini
photorealistic enhancement. Square saunas with windows (not barrel).
Clean daylight for structural clarity.

Resolution: 2560x1440 (2K) — sharp enough for AI input, faster than 4K
Samples: 2048 with tight adaptive threshold
Cameras: 8
Estimated render time: ~4-6 hours total on Mac mini M4 GPU

Usage: blender --background --python build_v11_rapid.py
"""
import bpy
import bmesh
import math
import os
import random
import time
from mathutils import Vector

random.seed(42)

print("=" * 60)
print("  SPONIC GARDEN v11 — AI-ASSIST STRUCTURAL RENDERS")
print("=" * 60)
print("  Resolution: 2560x1440 (2K)")
print("  Samples: 2048")
print("  Cameras: 8")
print("  Square saunas with windows (NOT barrel)")
print("  Clean daylight for structural clarity")
print("")
print("  Estimated render time: ~4-6 hours total")
print("=" * 60)
print("")

build_start = time.time()

# ═══════════════════════════════════════════
# CLEAN
# ═══════════════════════════════════════════
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for c in list(bpy.data.collections):
    if c.name != 'Scene Collection':
        bpy.data.collections.remove(c)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'METERS'

# ═══════════════════════════════════════════
# COLLECTIONS
# ═══════════════════════════════════════════
def col(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

C = {
    'site': col("Site"),
    'buildings': col("Buildings"),
    'trusses': col("Trusses"),
    'pool': col("Pool"),
    'spa': col("Spa"),
    'landscape': col("Landscape"),
    'plants': col("Plants"),
    'furniture': col("Furniture"),
    'string_lights': col("StringLights"),
    'paths': col("Paths"),
    'tech': col("Tech"),
    'interiors': col("Interiors"),
}

# ═══════════════════════════════════════════
# MATERIALS — industrial-garden palette
# ═══════════════════════════════════════════

def pbr(name, color, rough, metallic=0.0, alpha=1.0, emission=0.0, emit_color=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metallic
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        b.inputs['IOR'].default_value = 1.52
        m.surface_render_method = 'DITHERED'
    if emission > 0:
        b.inputs['Emission Strength'].default_value = emission
        if emit_color:
            b.inputs['Emission Color'].default_value = (*emit_color, 1.0)
    return m

def pbr_tex(name, c1, c2, rough, scale=8.0, metallic=0.0, bump_str=0.15):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nodes = nt.nodes
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metallic
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 10.0
    noise.inputs['Roughness'].default_value = 0.65
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*c1, 1.0)
    ramp.color_ramp.elements[1].color = (*c2, 1.0)
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = bump_str
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def pbr_corrugated(name, color1, color2, rough, metallic=0.5):
    """Corrugated metal — wave pattern bump for industrial walls"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nodes = nt.nodes
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metallic
    wave = nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'
    wave.inputs['Scale'].default_value = 40.0
    wave.inputs['Distortion'].default_value = 0.5
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 15.0
    noise.inputs['Detail'].default_value = 6.0
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*color1, 1.0)
    ramp.color_ramp.elements[1].color = (*color2, 1.0)
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.4
    nt.links.new(wave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def pbr_brick(name, brick_col, mortar_col, rough):
    """Brick wall material with procedural brick pattern"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nodes = nt.nodes
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs['Roughness'].default_value = rough
    brick = nodes.new('ShaderNodeTexBrick')
    brick.inputs['Color1'].default_value = (*brick_col, 1.0)
    brick.inputs['Color2'].default_value = (brick_col[0]*0.85, brick_col[1]*0.85, brick_col[2]*0.85, 1.0)
    brick.inputs['Mortar'].default_value = (*mortar_col, 1.0)
    brick.inputs['Scale'].default_value = 8.0
    brick.inputs['Mortar Size'].default_value = 0.02
    nt.links.new(brick.outputs['Color'], bsdf.inputs['Base Color'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.3
    nt.links.new(brick.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m


MAT = {
    # Industrial structure
    'steel_dark':    pbr_tex("Steel_Dark",   (0.18,0.18,0.20),(0.24,0.24,0.26), 0.35, 20, metallic=0.85),
    'steel_frame':   pbr("Steel_Frame",      (0.22,0.22,0.24), 0.30, metallic=0.90),
    'corrugated':    pbr_corrugated("Corrugated", (0.28,0.28,0.30),(0.35,0.35,0.38), 0.45, 0.7),
    'corrugated_dk': pbr_corrugated("Corrugated_Dk", (0.18,0.18,0.20),(0.24,0.24,0.26), 0.50, 0.65),
    'brick':         pbr_brick("Brick", (0.45,0.22,0.12),(0.60,0.55,0.50), 0.88),
    'brick_dk':      pbr_brick("Brick_Dk", (0.35,0.18,0.10),(0.50,0.45,0.40), 0.90),
    'concrete':      pbr_tex("Concrete", (0.48,0.46,0.42),(0.55,0.52,0.48), 0.92, 12),
    'concrete_lt':   pbr_tex("Concrete_Lt",(0.60,0.58,0.54),(0.66,0.64,0.60), 0.88, 10),

    # Wood
    'cedar':         pbr_tex("Cedar",     (0.42,0.28,0.14),(0.52,0.36,0.18), 0.70, 25),
    'cedar_lt':      pbr_tex("Cedar_Lt",  (0.55,0.40,0.22),(0.62,0.46,0.26), 0.65, 25),
    'cedar_dk':      pbr_tex("Cedar_Dk",  (0.30,0.20,0.10),(0.38,0.26,0.14), 0.72, 25),
    'cedar_aged':    pbr_tex("Cedar_Aged",(0.35,0.28,0.20),(0.42,0.34,0.26), 0.80, 20),

    # Glass
    'glass':         pbr("Glass",       (0.80,0.90,0.88), 0.02, alpha=0.18),
    'glass_tint':    pbr("Glass_Tint",  (0.50,0.72,0.68), 0.05, alpha=0.30),
    'glass_warm':    pbr("Glass_Warm",  (0.85,0.75,0.55), 0.03, alpha=0.25, emission=0.5, emit_color=(1.0,0.90,0.65)),

    # Roof
    'green_roof':    pbr_tex("Green_Roof",(0.14,0.28,0.08),(0.20,0.35,0.12), 0.88, 6, bump_str=0.25),
    'metal_roof':    pbr_corrugated("Metal_Roof",(0.25,0.25,0.28),(0.32,0.32,0.35), 0.50, 0.6),

    # Landscape
    'grass': None,
    'soil':          pbr_tex("Soil",     (0.22,0.14,0.06),(0.32,0.20,0.10), 0.92, 8),
    'mulch':         pbr_tex("Mulch",    (0.20,0.12,0.06),(0.28,0.18,0.10), 0.94, 6, bump_str=0.30),
    'gravel':        pbr_tex("Gravel",   (0.48,0.44,0.38),(0.58,0.54,0.46), 0.95, 22, bump_str=0.25),
    'sand':          pbr_tex("Sand",     (0.68,0.60,0.48),(0.74,0.66,0.54), 0.90, 10),

    # Water
    'water_pool':    pbr("Pool_Water",   (0.08,0.30,0.45), 0.01, alpha=0.60),
    'water_warm':    pbr("Warm_Water",   (0.10,0.28,0.38), 0.02, alpha=0.55),
    'water_cold':    pbr("Cold_Water",   (0.05,0.16,0.28), 0.01, alpha=0.50),

    # Fixtures
    'sauna_wd':      pbr_tex("Sauna_Wood",(0.50,0.34,0.16),(0.58,0.40,0.20), 0.55, 30),
    'deck':          pbr_tex("Deck",     (0.40,0.28,0.14),(0.48,0.34,0.18), 0.68, 30),
    'tile_pool':     pbr_tex("Tile_Pool",(0.62,0.65,0.67),(0.70,0.72,0.74), 0.60, 15),
    'tile_blue':     pbr_tex("Tile_Blue",(0.25,0.38,0.48),(0.30,0.44,0.55), 0.55, 15),
    'cushion':       pbr("Cushion",      (0.78,0.74,0.68), 0.85),
    'cushion_dk':    pbr("Cushion_Dk",   (0.26,0.28,0.24), 0.80),
    'fabric_tan':    pbr("Fabric_Tan",   (0.70,0.60,0.45), 0.82),

    # Plants
    'bark':          pbr_tex("Bark",     (0.20,0.13,0.06),(0.28,0.18,0.10), 0.92, 35),
    'foliage':       pbr_tex("Foliage",  (0.06,0.20,0.04),(0.13,0.30,0.08), 0.80, 5, bump_str=0.30),
    'foliage_lt':    pbr_tex("Foliage_Lt",(0.12,0.32,0.08),(0.20,0.40,0.12), 0.78, 5, bump_str=0.25),
    'hedge':         pbr_tex("Hedge",    (0.05,0.16,0.03),(0.10,0.22,0.06), 0.85, 4, bump_str=0.35),
    'vine':          pbr_tex("Vine",     (0.08,0.24,0.06),(0.14,0.32,0.10), 0.82, 3, bump_str=0.30),
    'pot_terra':     pbr_tex("Terracotta",(0.55,0.28,0.15),(0.62,0.34,0.20), 0.80, 12),
    'flowers_red':   pbr("Fl_Red",       (0.62,0.08,0.06), 0.75),
    'flowers_purp':  pbr("Fl_Purp",      (0.38,0.12,0.48), 0.75),
    'flowers_yel':   pbr("Fl_Yel",       (0.78,0.68,0.12), 0.75),
    'flowers_wht':   pbr("Fl_Wht",       (0.88,0.86,0.80), 0.75),
    'flowers_pink':  pbr("Fl_Pink",      (0.72,0.35,0.45), 0.75),

    # Lighting / tech
    'string_bulb':   pbr("String_Bulb",  (1.0,0.88,0.55), 0.2, emission=15.0, emit_color=(1.0,0.88,0.55)),
    'lantern':       pbr("Lantern",      (1.0,0.85,0.50), 0.2, emission=8.0, emit_color=(1.0,0.85,0.50)),
    'lantern_post':  pbr("Lantern_Post", (0.14,0.14,0.15), 0.50, metallic=0.7),
    'screen':        pbr("Screen",       (0.04,0.04,0.05), 0.10, emission=3.0),
    'speaker':       pbr("Speaker",      (0.10,0.10,0.11), 0.70),
    'sign_bg':       pbr("Sign_Bg",      (0.06,0.06,0.08), 0.60),
    'sign_text':     pbr("Sign_Text",    (0.90,0.88,0.80), 0.3, emission=1.5, emit_color=(0.90,0.88,0.80)),

    # Paths
    'stone_path':    pbr_tex("StonePath",(0.42,0.40,0.36),(0.52,0.50,0.46), 0.88, 18),
    'track':         pbr_tex("Track",    (0.52,0.32,0.18),(0.60,0.38,0.22), 0.85, 8),
    'stepping':      pbr_tex("Stepping", (0.50,0.48,0.44),(0.58,0.56,0.52), 0.85, 20),

    # Interior furniture
    'int_wood':      pbr_tex("Int_Wood", (0.45,0.32,0.18),(0.55,0.40,0.24), 0.65, 20),
}

# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════

def link_to(obj, collection):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    collection.objects.link(obj)

def box(name, cx, cy, cz, w, d, h, mat, coll, bevel=0.015):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, cz))
    o = bpy.context.active_object
    o.name = name
    o.dimensions = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        bpy.ops.object.modifier_add(type='BEVEL')
        o.modifiers['Bevel'].width = bevel
        o.modifiers['Bevel'].segments = 2
    o.data.materials.append(mat)
    link_to(o, coll)
    return o

def cyl(name, cx, cy, cz, radius, depth, mat, coll, smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=(cx, cy, cz))
    o = bpy.context.active_object
    o.name = name
    if smooth:
        bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    link_to(o, coll)
    return o


# ─── INDUSTRIAL BUILDING with exposed trusses ───
def make_industrial_building(name, cx, cy, w, d, h, wall_mat=None, has_trusses=True):
    """Building with corrugated walls + visible roof trusses like the concept art"""
    wm = wall_mat or MAT['corrugated']
    ft = 0.20
    wt = 0.20

    box(f"{name}_Floor", cx, cy, ft/2, w, d, ft, MAT['concrete'], C['buildings'], 0.02)

    box(f"{name}_WS", cx, cy-d/2+wt/2, ft+h/2, w, wt, h, wm, C['buildings'])
    box(f"{name}_WN", cx, cy+d/2-wt/2, ft+h/2, w, wt, h, wm, C['buildings'])
    box(f"{name}_WW", cx-w/2+wt/2, cy, ft+h/2, wt, d-2*wt, h, wm, C['buildings'])
    box(f"{name}_WE", cx+w/2-wt/2, cy, ft+h/2, wt, d-2*wt, h, wm, C['buildings'])

    # Corrugated metal roof
    box(f"{name}_Roof", cx, cy, ft+h+0.08, w+0.5, d+0.5, 0.12, MAT['metal_roof'], C['buildings'], 0.02)

    # Door
    box(f"{name}_Door", cx, cy-d/2-0.01, ft+1.1, 1.4, 0.06, 2.2, MAT['cedar_dk'], C['buildings'], 0.01)

    # Windows — warm glow from inside
    for side_y, sign in [(cy-d/2-0.02, -1), (cy+d/2+0.02, 1)]:
        for wx in range(int(w/3)):
            win_x = cx - w/4 + wx * (w/3)
            box(f"{name}_Win_{wx}_{sign}", win_x, side_y, ft+h*0.55, w/5, 0.02, h*0.25,
                MAT['glass_warm'], C['buildings'], 0)

    # Exposed roof trusses (A-frame steel)
    if has_trusses:
        num_trusses = max(3, int(d / 4))
        for i in range(num_trusses):
            ty = cy - d/2 + d/(num_trusses-1) * i
            ridge_h = ft + h + 0.5

            # Bottom chord (horizontal beam at wall top)
            box(f"{name}_Truss_Bot_{i}", cx, ty, ft+h, w-0.4, 0.08, 0.08,
                MAT['steel_frame'], C['trusses'], 0.005)

            # Left rafter
            rafter_len = math.sqrt((w/2)**2 + 0.5**2)
            rafter_angle = math.atan2(0.5, w/2)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(cx-w/4, ty, ft+h+0.25))
            rl = bpy.context.active_object
            rl.name = f"{name}_Rafter_L_{i}"
            rl.dimensions = (rafter_len, 0.06, 0.08)
            rl.rotation_euler[1] = rafter_angle
            bpy.ops.object.transform_apply(scale=True, rotation=True)
            rl.data.materials.append(MAT['steel_frame'])
            link_to(rl, C['trusses'])

            # Right rafter
            bpy.ops.mesh.primitive_cube_add(size=1, location=(cx+w/4, ty, ft+h+0.25))
            rr = bpy.context.active_object
            rr.name = f"{name}_Rafter_R_{i}"
            rr.dimensions = (rafter_len, 0.06, 0.08)
            rr.rotation_euler[1] = -rafter_angle
            bpy.ops.object.transform_apply(scale=True, rotation=True)
            rr.data.materials.append(MAT['steel_frame'])
            link_to(rr, C['trusses'])

            # King post (vertical center)
            box(f"{name}_King_{i}", cx, ty, ft+h+0.25, 0.06, 0.06, 0.5,
                MAT['steel_frame'], C['trusses'], 0.003)


def make_greenhouse(name, cx, cy, w, d, h):
    """Large greenhouse with steel frame, glass walls, exposed trusses — hero building"""
    ft = 0.20
    fs = 0.12

    box(f"{name}_Floor", cx, cy, ft/2, w, d, ft, MAT['concrete'], C['buildings'], 0.02)

    # Steel frame columns (perimeter + interior)
    col_x = [cx-w/2, cx-w/4, cx, cx+w/4, cx+w/2]
    col_y = [cy-d/2, cy, cy+d/2]
    for ix, x in enumerate(col_x):
        for iy, y in enumerate(col_y):
            box(f"{name}_Col_{ix}_{iy}", x, y, ft+h/2, fs, fs, h,
                MAT['steel_frame'], C['buildings'], 0.008)

    # Horizontal beams at top
    for y in col_y:
        box(f"{name}_HBeam_{y}", cx, y, ft+h, w, fs, fs, MAT['steel_frame'], C['buildings'], 0.005)
    for x in col_x:
        box(f"{name}_VBeam_{x}", x, cy, ft+h, fs, d, fs, MAT['steel_frame'], C['buildings'], 0.005)

    # Mid-height horizontal mullions
    for y in [cy-d/2, cy+d/2]:
        box(f"{name}_Mul_{y}", cx, y, ft+h*0.5, w, fs*0.7, fs*0.7, MAT['steel_frame'], C['buildings'], 0.004)
    for x in [cx-w/2, cx+w/2]:
        box(f"{name}_Mul_{x}", x, cy, ft+h*0.5, fs*0.7, d, fs*0.7, MAT['steel_frame'], C['buildings'], 0.004)

    # Glass panels
    for side, loc, dims in [
        ('S',(cx,cy-d/2,ft+h/2),(w,0.02,h)),
        ('N',(cx,cy+d/2,ft+h/2),(w,0.02,h)),
        ('W',(cx-w/2,cy,ft+h/2),(0.02,d,h)),
        ('E',(cx+w/2,cy,ft+h/2),(0.02,d,h)),
    ]:
        box(f"{name}_Glass_{side}", *loc, *dims, MAT['glass_tint'], C['buildings'], 0)

    # Glass roof
    box(f"{name}_GRoof", cx, cy, ft+h+0.02, w, d, 0.03, MAT['glass_tint'], C['buildings'], 0)

    # Exposed A-frame trusses (the signature look)
    num = max(4, int(d/3.5))
    peak_h = 1.2
    for i in range(num):
        ty = cy - d/2 + d/(num-1) * i
        box(f"{name}_TBot_{i}", cx, ty, ft+h+0.05, w-0.3, 0.08, 0.08,
            MAT['steel_frame'], C['trusses'], 0.004)
        for sign, lbl in [(-1, 'L'), (1, 'R')]:
            rl = math.sqrt((w/2)**2 + peak_h**2)
            ra = math.atan2(peak_h, w/2)
            bpy.ops.mesh.primitive_cube_add(size=1,
                location=(cx + sign*w/4, ty, ft+h+peak_h/2+0.05))
            r = bpy.context.active_object
            r.name = f"{name}_Raft_{lbl}_{i}"
            r.dimensions = (rl, 0.06, 0.08)
            r.rotation_euler[1] = sign * ra
            bpy.ops.object.transform_apply(scale=True, rotation=True)
            r.data.materials.append(MAT['steel_frame'])
            link_to(r, C['trusses'])

        box(f"{name}_King_{i}", cx, ty, ft+h+peak_h/2+0.05, 0.06, 0.06, peak_h,
            MAT['steel_frame'], C['trusses'], 0.003)

    # SPONIC GARDEN sign on south wall
    box(f"{name}_Sign_BG", cx, cy-d/2-0.04, ft+h-1.0, 8, 0.04, 0.8,
        MAT['sign_bg'], C['buildings'], 0.01)
    box(f"{name}_Sign_Text", cx, cy-d/2-0.06, ft+h-1.0, 7, 0.02, 0.4,
        MAT['sign_text'], C['buildings'], 0)


# ─── v11: SQUARE SAUNA with windows ───
def make_square_sauna(name, cx, cy, w=3.0, d=2.8, h=2.4, coll=None):
    """Square/rectangular sauna cabin with windows — NOT a barrel sauna.
    Cedar wood walls, metal roof, glass windows on two sides, chimney."""
    coll = coll or C['spa']
    ft = 0.10
    wt = 0.12

    # Floor
    box(f"{name}_Floor", cx, cy, ft/2, w, d, ft, MAT['deck'], coll, 0.01)

    # Cedar walls
    box(f"{name}_WS", cx, cy-d/2+wt/2, ft+h/2, w, wt, h, MAT['sauna_wd'], coll)
    box(f"{name}_WN", cx, cy+d/2-wt/2, ft+h/2, w, wt, h, MAT['sauna_wd'], coll)
    box(f"{name}_WW", cx-w/2+wt/2, cy, ft+h/2, wt, d-2*wt, h, MAT['sauna_wd'], coll)
    box(f"{name}_WE", cx+w/2-wt/2, cy, ft+h/2, wt, d-2*wt, h, MAT['sauna_wd'], coll)

    # Flat metal roof with slight overhang
    box(f"{name}_Roof", cx, cy, ft+h+0.06, w+0.3, d+0.3, 0.08, MAT['metal_roof'], coll, 0.01)

    # Door on south wall
    box(f"{name}_Door", cx, cy-d/2-0.01, ft+1.0, 0.8, 0.06, 2.0, MAT['cedar_dk'], coll, 0.01)

    # Windows — TWO on each long side (E/W), ONE on north wall
    # East windows
    for i in range(2):
        wy = cy - d/4 + i * d/2
        box(f"{name}_WinE_{i}", cx+w/2+0.01, wy, ft+h*0.55, 0.02, 0.6, h*0.35,
            MAT['glass_warm'], coll, 0)
    # West windows
    for i in range(2):
        wy = cy - d/4 + i * d/2
        box(f"{name}_WinW_{i}", cx-w/2-0.01, wy, ft+h*0.55, 0.02, 0.6, h*0.35,
            MAT['glass_warm'], coll, 0)
    # North window (single, wider)
    box(f"{name}_WinN", cx, cy+d/2+0.01, ft+h*0.55, 0.8, 0.02, h*0.35,
        MAT['glass_warm'], coll, 0)

    # Chimney/flue
    cyl(f"{name}_Chimney", cx+w/4, cy, ft+h+0.35, 0.08, 0.5, MAT['steel_frame'], coll)

    # Interior bench (visible through windows)
    box(f"{name}_Bench", cx, cy+d/4, ft+0.45, w*0.7, d*0.3, 0.06, MAT['cedar_lt'], coll, 0.005)

    # Interior warm light
    bpy.ops.object.light_add(type='POINT', location=(cx, cy, ft+h*0.7))
    light = bpy.context.active_object
    light.name = f"{name}_IntLight"
    light.data.energy = 15.0
    light.data.color = (1.0, 0.75, 0.40)
    light.data.shadow_soft_size = 0.5
    link_to(light, coll)


def make_organic_tree(name, cx, cy, coll=None, height=3.5, canopy_r=2.0):
    coll = coll or C['landscape']
    trunk_r = 0.08 + canopy_r*0.05
    bpy.ops.mesh.primitive_cone_add(radius1=trunk_r*1.4, radius2=trunk_r*0.5,
                                     depth=height, location=(cx, cy, height/2))
    trunk = bpy.context.active_object
    trunk.name = f"{name}_Trunk"
    bpy.ops.object.shade_smooth()
    trunk.data.materials.append(MAT['bark'])
    link_to(trunk, coll)

    for i, (dx,dy,dz,r,mk) in enumerate([
        (0,0,height+canopy_r*0.4,canopy_r,'foliage'),
        (-canopy_r*0.35,canopy_r*0.2,height+canopy_r*0.8,canopy_r*0.65,'foliage_lt'),
        (canopy_r*0.3,-canopy_r*0.15,height+canopy_r*0.6,canopy_r*0.75,'foliage'),
        (0,-canopy_r*0.25,height+canopy_r*0.95,canopy_r*0.45,'foliage_lt'),
    ]):
        bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=4,
                                               location=(cx+dx,cy+dy,dz))
        leaf = bpy.context.active_object
        leaf.name = f"{name}_C_{i}"
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(leaf.data)
        for v in bm.verts:
            v.co.x += random.uniform(-r*0.12, r*0.12)
            v.co.y += random.uniform(-r*0.12, r*0.12)
            v.co.z += random.uniform(-r*0.08, r*0.08)
        bmesh.update_edit_mesh(leaf.data)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.shade_smooth()
        leaf.data.materials.append(MAT[mk])
        link_to(leaf, coll)


def make_potted_plant(name, cx, cy, size=0.4, coll=None):
    coll = coll or C['plants']
    pot_h = size * 0.8
    bpy.ops.mesh.primitive_cone_add(radius1=size*0.5, radius2=size*0.35,
                                     depth=pot_h, location=(cx, cy, pot_h/2))
    pot = bpy.context.active_object
    pot.name = f"{name}_Pot"
    bpy.ops.object.shade_smooth()
    pot.data.materials.append(MAT['pot_terra'])
    link_to(pot, coll)

    bpy.ops.mesh.primitive_ico_sphere_add(radius=size*0.6, subdivisions=2,
                                           location=(cx, cy, pot_h+size*0.3))
    plant = bpy.context.active_object
    plant.name = f"{name}_Plant"
    plant.scale[2] = 0.7
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    plant.data.materials.append(MAT['foliage_lt'] if random.random() > 0.5 else MAT['foliage'])
    link_to(plant, coll)


def make_wall_vine(name, cx, cy, cz, width, height, face='S', coll=None):
    coll = coll or C['plants']
    if face in ('S', 'N'):
        box(f"{name}", cx, cy, cz, width, 0.15, height, MAT['vine'], coll, 0.02)
    else:
        box(f"{name}", cx, cy, cz, 0.15, width, height, MAT['vine'], coll, 0.02)


def make_string_lights(name, x1, y1, x2, y2, height=3.5, num_bulbs=8, coll=None):
    coll = coll or C['string_lights']
    dx, dy = x2-x1, y2-y1
    length = math.sqrt(dx*dx + dy*dy)
    cx, cy = (x1+x2)/2, (y1+y2)/2
    angle = math.atan2(dy, dx)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, height))
    wire = bpy.context.active_object
    wire.name = f"{name}_Wire"
    wire.dimensions = (length, 0.01, 0.01)
    wire.rotation_euler[2] = angle
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    wire.data.materials.append(MAT['lantern_post'])
    link_to(wire, coll)

    for i in range(num_bulbs):
        t = (i + 0.5) / num_bulbs
        bx = x1 + dx*t
        by = y1 + dy*t
        sag = -0.3 * math.sin(t * math.pi)
        bz = height + sag

        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, segments=8, ring_count=6,
                                              location=(bx, by, bz))
        bulb = bpy.context.active_object
        bulb.name = f"{name}_B_{i}"
        bpy.ops.object.shade_smooth()
        bulb.data.materials.append(MAT['string_bulb'])
        link_to(bulb, coll)

    bpy.ops.object.light_add(type='POINT', location=(cx, cy, height-0.2))
    light = bpy.context.active_object
    light.name = f"{name}_Glow"
    light.data.energy = 30.0
    light.data.color = (1.0, 0.88, 0.55)
    light.data.shadow_soft_size = 2.0
    link_to(light, coll)


def make_lantern(name, cx, cy, coll=None):
    coll = coll or C['string_lights']
    cyl(f"{name}_Post", cx, cy, 1.0, 0.02, 2.0, MAT['lantern_post'], coll)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.10, location=(cx, cy, 2.1))
    b = bpy.context.active_object
    b.name = f"{name}_Bulb"
    bpy.ops.object.shade_smooth()
    b.data.materials.append(MAT['lantern'])
    link_to(b, coll)
    bpy.ops.object.light_add(type='POINT', location=(cx, cy, 2.1))
    l = bpy.context.active_object
    l.name = f"{name}_L"
    l.data.energy = 12.0
    l.data.color = (1.0, 0.85, 0.50)
    l.data.shadow_soft_size = 0.3
    link_to(l, coll)


def make_hedge(name, cx, cy, length, width=0.8, height=1.2, along_x=True, coll=None):
    coll = coll or C['landscape']
    if along_x:
        box(name, cx, cy, height/2, length, width, height, MAT['hedge'], coll, 0.06)
    else:
        box(name, cx, cy, height/2, width, length, height, MAT['hedge'], coll, 0.06)


def make_shrub(name, cx, cy, r=0.5, coll=None):
    coll = coll or C['landscape']
    bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=2, location=(cx, cy, r*0.6))
    s = bpy.context.active_object
    s.name = name
    s.scale[2] = 0.6
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(s.data)
    for v in bm.verts:
        v.co += Vector((random.uniform(-r*0.1,r*0.1), random.uniform(-r*0.1,r*0.1), random.uniform(-r*0.06,r*0.06)))
    bmesh.update_edit_mesh(s.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_smooth()
    s.data.materials.append(MAT['hedge'])
    link_to(s, coll)


def make_bench(name, cx, cy, coll=None):
    coll = coll or C['furniture']
    box(f"{name}_Se", cx, cy, 0.45, 1.5, 0.45, 0.06, MAT['cedar_lt'], coll, 0.005)
    box(f"{name}_Bk", cx, cy-0.18, 0.70, 1.5, 0.06, 0.50, MAT['cedar_lt'], coll, 0.005)
    for dx in [-0.6, 0.6]:
        for dy in [-0.15, 0.15]:
            box(f"{name}_L_{dx}_{dy}", cx+dx, cy+dy, 0.22, 0.05, 0.05, 0.44, MAT['steel_frame'], coll, 0.003)


def make_walkway(name, x1, y1, x2, y2):
    dx, dy = x2-x1, y2-y1
    length = math.sqrt(dx*dx + dy*dy)
    cx, cy = (x1+x2)/2, (y1+y2)/2
    angle = math.atan2(dy, dx)
    post_h = 3.0
    ft = 0.20

    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, ft/2))
    path = bpy.context.active_object
    path.name = f"{name}_Path"
    path.dimensions = (length, 2.4, ft)
    path.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    path.data.materials.append(MAT['stone_path'])
    link_to(path, C['paths'])

    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, post_h+0.06))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof"
    roof.dimensions = (length, 2.8, 0.06)
    roof.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    roof.data.materials.append(MAT['cedar'])
    link_to(roof, C['paths'])

    for t in [0.12, 0.5, 0.88]:
        px = x1+dx*t
        py = y1+dy*t
        for off in [-1.0, 1.0]:
            ox = -math.sin(angle)*off
            oy = math.cos(angle)*off
            box(f"{name}_P_{t}_{off}", px+ox, py+oy, post_h/2, 0.12, 0.12, post_h,
                MAT['cedar'], C['paths'], 0.008)


def make_interior_area_light(name, cx, cy, cz, size_x=3, size_y=3, energy=5.0):
    bpy.ops.object.light_add(type='AREA', location=(cx, cy, cz))
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    light.data.color = (1.0, 0.78, 0.50)
    light.data.size = size_x
    light.data.size_y = size_y
    light.data.shape = 'RECTANGLE'
    link_to(light, C['interiors'])
    return light


# ═══════════════════════════════════════════
# BUILD SCENE
# ═══════════════════════════════════════════
print("[1/14] Site...")

bpy.ops.mesh.primitive_plane_add(size=250, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"
mat_grass = bpy.data.materials.new("Ground_Grass")
mat_grass.use_nodes = True
nt = mat_grass.node_tree
nodes = nt.nodes
for n in nodes: nodes.remove(n)
out = nodes.new('ShaderNodeOutputMaterial')
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
n1 = nodes.new('ShaderNodeTexNoise')
n1.inputs['Scale'].default_value = 35.0
n1.inputs['Detail'].default_value = 14.0
n2 = nodes.new('ShaderNodeTexNoise')
n2.inputs['Scale'].default_value = 5.0
mix = nodes.new('ShaderNodeMixRGB')
mix.blend_type = 'OVERLAY'
mix.inputs['Fac'].default_value = 0.25
r1 = nodes.new('ShaderNodeValToRGB')
r1.color_ramp.elements[0].color = (0.03,0.08,0.01,1)
r1.color_ramp.elements[1].color = (0.09,0.22,0.04,1)
r2 = nodes.new('ShaderNodeValToRGB')
r2.color_ramp.elements[0].color = (0.06,0.14,0.02,1)
r2.color_ramp.elements[1].color = (0.12,0.28,0.06,1)
nt.links.new(n1.outputs['Fac'], r1.inputs['Fac'])
nt.links.new(n2.outputs['Fac'], r2.inputs['Fac'])
nt.links.new(r1.outputs['Color'], mix.inputs['Color1'])
nt.links.new(r2.outputs['Color'], mix.inputs['Color2'])
nt.links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.92
bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.30
nt.links.new(n1.outputs['Fac'], bump.inputs['Height'])
nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
ground.data.materials.append(mat_grass)
MAT['grass'] = mat_grass
link_to(ground, C['site'])
print("  Done")

# ═══════════════════════════════════════════
print("[2/14] Buildings...")

# 1. Welcome Center — brick + industrial
make_industrial_building("Welcome", 0, -18, 10, 8, 4.5, wall_mat=MAT['brick'])

# 2. Greenhouse — the HERO building
make_greenhouse("Greenhouse", 0, 25, 20, 15, 5.5)

# 3. Dining Hall — brick walls, warm
make_industrial_building("Dining", -22, 8, 15, 10, 4.5, wall_mat=MAT['brick_dk'])

# 4. Education — corrugated industrial
make_industrial_building("Education", 22, 10, 10, 10, 4.5, wall_mat=MAT['corrugated'])

# 5. Maker Studio — dark industrial
make_industrial_building("Maker", -22, -8, 10, 10, 5.0, wall_mat=MAT['corrugated_dk'])

# 6. Movement — glass
make_greenhouse("Movement", 22, -8, 12, 10, 4.5)

# 7. Spa House — cedar + brick
make_industrial_building("SpaHouse", 12, -28, 10, 10, 3.8, wall_mat=MAT['cedar_aged'])

# Coffee bar
box("Coffee_Floor", -30, -4, 0.1, 6, 5, 0.2, MAT['concrete'], C['buildings'], 0.02)
box("Coffee_Roof", -30, -4, 3.15, 7, 6, 0.08, MAT['cedar'], C['buildings'], 0.02)
for dx,dy in [(-3,-2.5),(3,-2.5),(-3,2.5),(3,2.5)]:
    box(f"Cf_P_{dx}_{dy}", -30+dx, -4+dy, 1.55, 0.12, 0.12, 3.1, MAT['cedar'], C['buildings'])
box("Cf_Counter", -30, -3, 0.55, 4, 0.6, 0.9, MAT['cedar_lt'], C['buildings'])

for i in range(4):
    sx = -31.5 + i * 1.0
    cyl(f"Cf_Stool_{i}_Leg", sx, -2.4, 0.35, 0.02, 0.7, MAT['steel_frame'], C['furniture'])
    cyl(f"Cf_Stool_{i}_Seat", sx, -2.4, 0.72, 0.15, 0.04, MAT['cedar_lt'], C['furniture'])

print("  Done")

# ═══════════════════════════════════════════
print("[3/14] Pool...")

PX, PY = -8, -32
box("Pool_Deck", PX, PY, 0.08, 22, 14, 0.16, MAT['sand'], C['pool'], 0.02)
box("Pool_Shell", PX-2, PY, -0.3, 14, 8, 1.5, MAT['tile_blue'], C['pool'], 0.03)
bpy.ops.mesh.primitive_plane_add(size=1, location=(PX-2, PY, 0.05))
pw = bpy.context.active_object; pw.name = "Pool_Water"
pw.dimensions = (13.6, 7.6, 0)
bpy.ops.object.transform_apply(scale=True)
pw.data.materials.append(MAT['water_pool'])
link_to(pw, C['pool'])

for loc,dims in [
    ((PX-2,PY-4.2,0.14),(14.4,0.45,0.14)),
    ((PX-2,PY+4.2,0.14),(14.4,0.45,0.14)),
    ((PX-9.2,PY,0.14),(0.45,8.4,0.14)),
    ((PX+5.2,PY,0.14),(0.45,8.4,0.14)),
]:
    box("Pool_Cope", *loc, *dims, MAT['stepping'], C['pool'], 0.01)

for i in range(3):
    box(f"Pool_Step_{i}", PX+4, PY+4-i*0.3, 0.02-i*0.25, 3, 0.5, 0.15, MAT['tile_pool'], C['pool'], 0.01)

# Lounges + umbrellas
for i in range(6):
    lx = PX-7+i*2.5
    box(f"Lng_{i}_Fr", lx, PY+5.8, 0.28, 0.65, 1.8, 0.05, MAT['steel_frame'], C['pool'], 0.005)
    box(f"Lng_{i}_Cu", lx, PY+5.8, 0.34, 0.58, 1.5, 0.08, MAT['cushion'], C['pool'], 0.008)

for i, ux in enumerate([PX-5, PX-0.5, PX+4]):
    cyl(f"Umb_{i}_P", ux, PY+5.8, 1.4, 0.03, 2.8, MAT['lantern_post'], C['pool'])
    bpy.ops.mesh.primitive_cone_add(radius1=1.6, radius2=0, depth=0.6, location=(ux, PY+5.8, 2.85))
    u = bpy.context.active_object; u.name = f"Umb_{i}_T"
    u.rotation_euler[0] = math.radians(180)
    bpy.ops.object.transform_apply(rotation=True)
    bpy.ops.object.shade_smooth()
    u.data.materials.append(MAT['fabric_tan'])
    link_to(u, C['pool'])

print("  Done")

# ═══════════════════════════════════════════
print("[4/14] Spa — v11: SQUARE SAUNAS with windows...")

SX, SY = 22, -28
box("Spa_Deck", SX, SY, 0.08, 16, 12, 0.16, MAT['deck'], C['spa'], 0.02)

# v11: TWO square saunas instead of one barrel sauna
make_square_sauna("Sauna_1", SX-3, SY+2, w=3.0, d=2.8, h=2.4)
make_square_sauna("Sauna_2", SX+3, SY+2, w=2.6, d=2.4, h=2.2)

# Cold plunge
cp = box("CPlunge", SX, SY-2, 0.2, 3.0, 2.0, 1.2, MAT['concrete'], C['spa'], 0.02)
cp.modifiers.new('Sol','SOLIDIFY'); cp.modifiers['Sol'].thickness = 0.1; cp.modifiers['Sol'].offset = -1
bpy.ops.mesh.primitive_plane_add(size=1, location=(SX, SY-2, 0.7))
cpw = bpy.context.active_object; cpw.name = "CPlunge_W"; cpw.dimensions = (2.8, 1.8, 0)
bpy.ops.object.transform_apply(scale=True); cpw.data.materials.append(MAT['water_cold']); link_to(cpw, C['spa'])

# Hot tubs
for i, (hx,hy) in enumerate([(SX-3,SY-4),(SX+3,SY-4)]):
    ht = cyl(f"HT_{i}", hx, hy, 0.55, 1.2, 0.9, MAT['cedar_lt'], C['spa'])
    bpy.ops.object.modifier_add(type='SOLIDIFY'); ht.modifiers['Solidify'].thickness = 0.10; ht.modifiers['Solidify'].offset = -1
    cyl(f"HT_{i}_W", hx, hy, 0.85, 1.05, 0.02, MAT['water_warm'], C['spa'])

make_bench("SpaBench1", SX, SY-6, coll=C['spa'])
print("  Done")

# ═══════════════════════════════════════════
print("[5/14] Landscape...")

# Garden beds (NW)
for row in range(4):
    for ci in range(6):
        x = -38 + ci*3.8
        y = 20 + row*3.5
        box(f"Bed_{row}_{ci}", x, y, 0.25, 3.0, 1.2, 0.5, MAT['cedar_aged'], C['landscape'])
        box(f"Soil_{row}_{ci}", x, y, 0.48, 2.9, 1.1, 0.04, MAT['soil'], C['landscape'], 0)
        for pr in range(3):
            py_off = -0.3 + pr * 0.3
            cyl(f"PlantRow_{row}_{ci}_{pr}", x, y + py_off, 0.55, 0.04, 0.12,
                MAT['foliage_lt'] if pr % 2 == 0 else MAT['foliage'], C['landscape'])

# Orchard
for i in range(12):
    make_organic_tree(f"Orch_{i}", 28+(i%4)*5, 22+(i//4)*5, height=3.5+random.uniform(0,1))

# Scattered trees
for i, (tx,ty) in enumerate([
    (-35,-15),(-35,15),(35,15),(-12,-40),(14,-40),(-38,0),(38,0),
    (-15,38),(15,38),(-28,-22),(28,28),(-40,-25),(40,10),(-8,40),(8,40),
    (-25,32),(25,-18),(-18,-35),(30,-18),
]):
    make_organic_tree(f"D_{i}", tx, ty, height=2.5+random.uniform(0,1.5), canopy_r=1.2+random.uniform(0,0.8))

# Hedges
make_hedge("H_EntW", -4, -15, 6, along_x=False)
make_hedge("H_EntE", 4, -15, 6, along_x=False)
make_hedge("H_PoolN", PX, PY+7.5, 22, height=1.0)
make_hedge("H_PoolS", PX, PY-7.5, 22, height=1.0)
make_hedge("H_SpaN", SX, SY+6.5, 16, height=1.0)
make_hedge("H_GarS", -19, 18, 24, height=0.9)
make_hedge("H_GarN", -19, 35, 24, height=0.9)

# Shrubs at entrances
for sx,sy in [(-3,-14),(3,-14),(-14,3),(-14,13),(17,5),(17,15),(-17,-3),(-17,-13),(16,-3),(16,-13),(-33,-7),(-27,-7)]:
    make_shrub(f"Sh_{sx}_{sy}", sx, sy, r=0.4+random.uniform(0,0.2))

# Flowers
fl_mats = [MAT['flowers_red'],MAT['flowers_purp'],MAT['flowers_yel'],MAT['flowers_wht'],MAT['flowers_pink']]
for i in range(50):
    a = math.radians(i*7.2)
    r = 7+random.uniform(-0.5,0.5)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.22, subdivisions=1, location=(math.cos(a)*r, math.sin(a)*r, 0.11))
    fl = bpy.context.active_object; fl.name = f"Fl_{i}"; fl.scale[2] = 0.35
    bpy.ops.object.transform_apply(scale=True); fl.data.materials.append(fl_mats[i%5]); link_to(fl, C['landscape'])

# Extra flower clusters near buildings
extra_flower_spots = [
    (-15, 3), (-15, 13), (17, 5), (17, 15), (-30, -8), (-30, 0),
    (-5, 17), (5, 17), (PX-10, PY), (PX+6, PY), (SX-8, SY+6), (SX+8, SY+6),
]
for fi, (fx, fy) in enumerate(extra_flower_spots):
    for fj in range(3):
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.18, subdivisions=1,
            location=(fx + random.uniform(-0.5, 0.5), fy + random.uniform(-0.5, 0.5), 0.09))
        efl = bpy.context.active_object
        efl.name = f"ExFl_{fi}_{fj}"
        efl.scale[2] = 0.3
        bpy.ops.object.transform_apply(scale=True)
        efl.data.materials.append(fl_mats[(fi+fj) % 5])
        link_to(efl, C['landscape'])

# Fire pit
cyl("FirePit", -24, -24, 0.25, 0.7, 0.5, MAT['concrete'], C['landscape'])
cyl("FireGlow", -24, -24, 0.45, 0.35, 0.08, MAT['lantern'], C['landscape'])
bpy.ops.mesh.primitive_torus_add(major_radius=2.5, minor_radius=0.28, location=(-24,-24,0.48))
sr = bpy.context.active_object; sr.name = "FireSeat"; sr.data.materials.append(MAT['cedar']); link_to(sr, C['landscape'])

# Fountain
fount = cyl("Fount", 0, 0, 0.3, 2.5, 0.6, MAT['concrete'], C['landscape'])
fount.modifiers.new('Sol','SOLIDIFY'); fount.modifiers['Sol'].thickness = 0.15; fount.modifiers['Sol'].offset = -1
cyl("FountW", 0, 0, 0.45, 2.3, 0.02, MAT['water_pool'], C['landscape'])
cyl("FountJ", 0, 0, 0.8, 0.06, 0.7, MAT['concrete_lt'], C['landscape'])

rp = box("ReflPool", 0, 38, 0.0, 14, 3, 0.5, MAT['concrete'], C['landscape'], 0.02)
rp.modifiers.new('Sol','SOLIDIFY'); rp.modifiers['Sol'].thickness = 0.1; rp.modifiers['Sol'].offset = -1
bpy.ops.mesh.primitive_plane_add(size=1, location=(0,38,0.2))
rpw = bpy.context.active_object; rpw.name = "ReflW"; rpw.dimensions = (13.6,2.6,0)
bpy.ops.object.transform_apply(scale=True); rpw.data.materials.append(MAT['water_pool']); link_to(rpw, C['landscape'])

print("  Done")

# ═══════════════════════════════════════════
print("[6/14] Potted plants + wall vines...")

pot_spots = [
    (1.5,-14), (-1.5,-14), (3,-14.5), (-3,-14.5),
    (-14.5,3), (-14.5,5), (-14.5,11),
    (17.5,5), (17.5,8), (17.5,13),
    (-17.5,-3), (-17.5,-6),
    (16.5,-3), (16.5,-6),
    (7,-24), (17,-24),
    (-32,-1.5), (-28,-1.5), (-32,-6.5), (-28,-6.5),
    (-10,17.5), (-7,17.5), (-4,17.5), (4,17.5), (7,17.5), (10,17.5),
    (PX-10,PY-2), (PX-10,PY+2), (PX+6,PY-2), (PX+6,PY+2),
    (3,3), (-3,3), (3,-3), (-3,-3),
    (2.5,-14.5), (-2.5,-14.5), (0,-14.8),
    (-14.8,7), (-14.8,9),
    (17.8,7), (17.8,11),
    (-17.8,-5), (-17.8,-8),
    (16.8,-5), (16.8,-8),
    (9,-24), (15,-24), (5,-26), (19,-26),
    (-34,-3), (-26,-3), (-34,-5), (-26,-5),
    (-8,17.5), (-2,17.5), (2,17.5), (6,17.5), (8,17.5),
    (-10,32.5), (-7,32.5), (-4,32.5), (4,32.5), (7,32.5), (10,32.5),
    (PX-8,PY-5), (PX-4,PY-5), (PX,PY-5), (PX+4,PY-5),
    (5,5), (-5,5), (5,-5), (-5,-5), (6,0), (-6,0), (0,6), (0,-6),
]
for i, (px,py) in enumerate(pot_spots):
    make_potted_plant(f"Pot_{i}", px, py, size=0.3+random.uniform(0,0.2))

# Climbing vines
make_wall_vine("Vine_Welcome_S", 3, -22.1, 2.5, 3, 3, 'S')
make_wall_vine("Vine_Welcome_E", 5.1, -18, 2.5, 4, 3, 'E')
make_wall_vine("Vine_Welcome_W", -5.1, -18, 2.5, 4, 3, 'W')
make_wall_vine("Vine_Dining_S", -20, 2.9, 2.5, 5, 3, 'S')
make_wall_vine("Vine_Dining_W", -29.6, 8, 2.5, 4, 3, 'W')
make_wall_vine("Vine_Dining_N", -20, 13.1, 2.5, 5, 3, 'N')
make_wall_vine("Vine_GH_S", -5, 17.4, 3.0, 6, 3.5, 'S')
make_wall_vine("Vine_GH_E", 10.1, 25, 3.0, 8, 3.5, 'E')
make_wall_vine("Vine_GH_W", -10.1, 25, 3.0, 8, 3.5, 'W')
make_wall_vine("Vine_GH_N", 5, 32.6, 3.0, 6, 3.5, 'N')
make_wall_vine("Vine_Maker_N", -22, -2.9, 3.0, 4, 3, 'N')
make_wall_vine("Vine_Maker_S", -22, -13.1, 3.0, 4, 3, 'S')
make_wall_vine("Vine_Spa_W", 6.9, -28, 2.0, 5, 2.5, 'W')
make_wall_vine("Vine_Spa_E", 17.1, -28, 2.0, 5, 2.5, 'E')
make_wall_vine("Vine_Edu_W", 16.9, 10, 2.5, 4, 3, 'W')
make_wall_vine("Vine_Edu_E", 27.1, 10, 2.5, 4, 3, 'E')
make_wall_vine("Vine_Move_S", 22, -13.1, 2.5, 4, 3, 'S')

print("  Done")

# ═══════════════════════════════════════════
print("[7/14] Interior elements...")

# Greenhouse interior
gh_cx, gh_cy, gh_ft = 0, 25, 0.20
for ti in range(4):
    tx = gh_cx - 6 + ti * 4
    box(f"GH_Table_{ti}", tx, gh_cy - 2, gh_ft + 0.45, 2.5, 0.8, 0.06, MAT['int_wood'], C['interiors'], 0.005)
    for lx, ly in [(-1.0, -0.3), (1.0, -0.3), (-1.0, 0.3), (1.0, 0.3)]:
        box(f"GH_TLeg_{ti}_{lx}_{ly}", tx + lx, gh_cy - 2 + ly, gh_ft + 0.22, 0.05, 0.05, 0.44,
            MAT['steel_frame'], C['interiors'], 0.002)
    for pi in range(2):
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.25, subdivisions=2,
            location=(tx - 0.5 + pi * 1.0, gh_cy - 2, gh_ft + 0.65))
        ip = bpy.context.active_object
        ip.name = f"GH_IntPlant_{ti}_{pi}"
        ip.scale[2] = 0.6
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        ip.data.materials.append(MAT['foliage_lt'] if pi % 2 == 0 else MAT['foliage'])
        link_to(ip, C['interiors'])

for si in range(3):
    sy = gh_cy - 5 + si * 5
    box(f"GH_Shelf_W_{si}", gh_cx - 9, sy, gh_ft + 1.2, 1.5, 0.4, 0.04, MAT['int_wood'], C['interiors'], 0.003)
    box(f"GH_Shelf_E_{si}", gh_cx + 9, sy, gh_ft + 1.2, 1.5, 0.4, 0.04, MAT['int_wood'], C['interiors'], 0.003)

# Movement studio interior
mv_cx, mv_cy, mv_ft = 22, -8, 0.20
box("MV_Bench", mv_cx, mv_cy - 3, mv_ft + 0.25, 8, 0.6, 0.06, MAT['int_wood'], C['interiors'], 0.005)
box("MV_Shelf", mv_cx, mv_cy + 3, mv_ft + 1.0, 8, 0.4, 0.04, MAT['int_wood'], C['interiors'], 0.003)

print("  Done")

# ═══════════════════════════════════════════
print("[8/14] Seating...")

box("DPatio", -30, 14, 0.05, 8, 8, 0.1, MAT['stone_path'], C['furniture'], 0.01)
for i in range(4):
    tx = -32+(i%2)*4; ty = 12+(i//2)*4
    cyl(f"DTbl_{i}", tx, ty, 0.72, 0.5, 0.04, MAT['cedar_lt'], C['furniture'])
    cyl(f"DTblL_{i}", tx, ty, 0.38, 0.05, 0.72, MAT['steel_frame'], C['furniture'])

for i in range(4):
    make_bench(f"CBench_{i}", math.cos(math.radians(i*90+45))*5, math.sin(math.radians(i*90+45))*5, coll=C['furniture'])

box("YogaDeck", 35, -5, 0.05, 12, 12, 0.1, MAT['deck'], C['furniture'], 0.01)

print("  Done")

# ═══════════════════════════════════════════
print("[9/14] String lights...")

string_routes = [
    (-4, -14, -15, 3, 4.0),
    (-4, -15, -17, -4, 4.0),
    (4, -14, 16, -5, 4.0),
    (4, -14, 17, 5, 4.0),
    (-10, 17, 10, 17, 4.5),
    (-10, 33, 10, 33, 4.5),
    (-33, -1, -27, -1, 3.5),
    (-33, -7, -27, -7, 3.5),
    (PX-10, PY-7, PX-10, PY+7, 3.0),
    (PX+6, PY-7, PX+6, PY+7, 3.0),
    (SX-8, SY-6, SX-8, SY+6, 3.0),
    (SX+8, SY-6, SX+8, SY+6, 3.0),
    (-5, -5, 5, 5, 4.0),
    (5, -5, -5, 5, 4.0),
    (-28, -28, -20, -20, 3.0),
    (-20, -28, -28, -20, 3.0),
    (-10, 25, 10, 25, 5.0),
    (-27, 3, -33, -1, 3.5),
    (29, -11, 41, -11, 3.0),
    (29, 1, 41, 1, 3.0),
    (PX+6, PY, SX-8, SY, 3.0),
    (-4, -22, 4, -22, 3.5),
]
for i, (x1,y1,x2,y2,h) in enumerate(string_routes):
    make_string_lights(f"SL_{i}", x1, y1, x2, y2, height=h, num_bulbs=6)

print(f"  Done: {len(string_routes)} string light runs")

# ═══════════════════════════════════════════
print("[10/14] Path lanterns...")

for i, (lx,ly) in enumerate([
    (5,0),(-5,0),(0,5),(0,-5),(3.5,3.5),(-3.5,3.5),(3.5,-3.5),(-3.5,-3.5),
    (PX-10,PY),(PX+6,PY),(SX-8,SY),(SX+8,SY),(-34,14),(-26,14),
    (-38,17),(-18,17),(-6,-12),(6,-12),(-28,-24),(-20,-24),
]):
    make_lantern(f"Ln_{i}", lx, ly)

print("  Done")

# ═══════════════════════════════════════════
print("[11/14] Walkways...")

make_walkway("WK1", -4, -14, -15, 3)
make_walkway("WK2", -4, -15, -17, -4)
make_walkway("WK3", 4, -14, 16, -5)
make_walkway("WK4", 4, -14, 17, 5)
make_walkway("WK5", -15, 12, -8, 18)
make_walkway("WK6", 17, 14, 9, 18)
make_walkway("WK7", 4, -22, PX+8, PY+7)
make_walkway("WK8", 10, -22, SX-6, SY+6)

for ad in range(0, 360, 45):
    a = math.radians(ad)
    x2,y2 = math.cos(a)*14, math.sin(a)*14
    length = math.sqrt(x2*x2+y2*y2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x2/2, y2/2, 0.025))
    rp = bpy.context.active_object; rp.name = f"RP_{ad}"
    rp.dimensions = (length, 1.6, 0.05)
    rp.rotation_euler = (0, 0, math.atan2(y2, x2))
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    rp.data.materials.append(MAT['stone_path']); link_to(rp, C['paths'])

# Running circuit
S = 90.0; INS = 5.0
for side,loc,dims in [("S",(0,-S/2+INS,0.03),(S-2*INS,1.8,0.04)),("N",(0,S/2-INS,0.03),(S-2*INS,1.8,0.04)),
                       ("W",(-S/2+INS,0,0.03),(1.8,S-2*INS,0.04)),("E",(S/2-INS,0,0.03),(1.8,S-2*INS,0.04))]:
    box(f"Circ_{side}",*loc,*dims,MAT['track'],C['paths'],0.005)

print("  Done")

# ═══════════════════════════════════════════
print("[12/14] Interior lights...")

make_interior_area_light("GH_IntLight_1", 0, 22, 4.0, size_x=6, size_y=4, energy=5.0)
make_interior_area_light("GH_IntLight_2", 0, 28, 4.0, size_x=6, size_y=4, energy=5.0)
make_interior_area_light("MV_IntLight", 22, -8, 3.5, size_x=4, size_y=3, energy=5.0)
make_interior_area_light("Dining_IntLight", -22, 8, 3.5, size_x=5, size_y=4, energy=5.0)
make_interior_area_light("Welcome_IntLight", 0, -18, 3.5, size_x=4, size_y=3, energy=5.0)
make_interior_area_light("Edu_IntLight", 22, 10, 3.5, size_x=4, size_y=3, energy=5.0)
make_interior_area_light("Maker_IntLight", -22, -8, 3.5, size_x=4, size_y=3, energy=5.0)
make_interior_area_light("SpaH_IntLight", 12, -28, 2.8, size_x=3, size_y=3, energy=5.0)

print("  Done")

# ═══════════════════════════════════════════
print("[13/14] Subdivision surfaces + render settings...")

subdiv_count = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mod = obj.modifiers.new('Subdiv', 'SUBSURF')
        mod.levels = 2
        mod.render_levels = 2
        subdiv_count += 1
print(f"  Added Subdivision Surface (level 2) to {subdiv_count} mesh objects")

# ═══════════════════════════════════════════
# RENDER SETTINGS — quality but faster than v10
# ═══════════════════════════════════════════
scene.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices: d.use = True
    scene.cycles.device = 'GPU'
    print("  GPU (Metal) rendering enabled")
except:
    scene.cycles.device = 'CPU'
    print("  WARNING: Falling back to CPU rendering")

# Resolution: 2K (good balance for AI input)
scene.render.resolution_x = 2560
scene.render.resolution_y = 1440

# Samples: 2048 with adaptive
scene.cycles.samples = 2048
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.005

# Denoiser
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.denoising_prefilter = 'ACCURATE'

# Bounces — high quality
scene.cycles.max_bounces = 24
scene.cycles.diffuse_bounces = 6
scene.cycles.glossy_bounces = 8
scene.cycles.transmission_bounces = 12
scene.cycles.volume_bounces = 2

# Enable caustics for glass/water
scene.cycles.caustics_reflective = True
scene.cycles.caustics_refractive = True

# Tile size optimized for Metal GPU
scene.cycles.tile_size = 256

# Film
scene.render.film_transparent = False
scene.cycles.film_exposure = 1.0

# Color management: AgX with Punchy look
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Punchy'
    print("  Color: AgX Punchy")
except:
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except:
        try:
            scene.view_settings.look = 'AgX - Medium Contrast'
        except:
            pass
scene.view_settings.exposure = 0.3

# ═══════════════════════════════════════════
# CLEAN DAYLIGHT — structural clarity
# ═══════════════════════════════════════════
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
for n in wn: wn.remove(n)

sky = wn.new('ShaderNodeTexSky')
sky.sky_type = 'HOSEK_WILKIE'
sky.sun_elevation = math.radians(50)
sky.sun_rotation = math.radians(-30)
try: sky.turbidity = 2.0
except: pass

bg = wn.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value = 1.2
out = wn.new('ShaderNodeOutputWorld')
wl.new(sky.outputs['Color'], bg.inputs['Color'])
wl.new(bg.outputs['Background'], out.inputs['Surface'])

# Key sun — neutral daylight
bpy.ops.object.light_add(type='SUN', location=(30, -30, 50))
sun = bpy.context.active_object; sun.name = "Sun"
sun.data.energy = 4.0
sun.data.color = (1.0, 0.97, 0.92)
sun.data.angle = math.radians(0.5)
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))

# Fill from opposite
bpy.ops.object.light_add(type='SUN', location=(-20, 20, 40))
fill = bpy.context.active_object; fill.name = "Fill"
fill.data.energy = 1.5
fill.data.color = (0.90, 0.92, 1.0)
fill.data.angle = math.radians(3.0)
fill.rotation_euler = (math.radians(55), math.radians(-10), math.radians(150))

print("  Done: Cycles 2048spp, 2K, clean daylight")

# ═══════════════════════════════════════════
print("[14/14] Cameras (8 total)...")

# 1. CAM_aerial — orthographic overview
bpy.ops.object.camera_add(location=(0, 0, 85))
cam1 = bpy.context.active_object; cam1.name = "CAM_aerial"
cam1.data.type = 'ORTHO'; cam1.data.ortho_scale = 100

# 2. CAM_hero — main perspective
bpy.ops.object.camera_add(location=(42, -42, 22))
cam2 = bpy.context.active_object; cam2.name = "CAM_hero"
cam2.data.lens = 24; cam2.data.sensor_width = 36; cam2.data.clip_end = 500
cam2.rotation_euler = (math.radians(70), 0, math.radians(38))

# 3. CAM_pool_spa — pool and spa area with DOF
bpy.ops.object.camera_add(location=(30, -50, 10))
cam3 = bpy.context.active_object; cam3.name = "CAM_pool_spa"
cam3.data.lens = 32; cam3.data.sensor_width = 36; cam3.data.clip_end = 500
cam3.rotation_euler = (math.radians(82), 0, math.radians(12))
cam3.data.dof.use_dof = True; cam3.data.dof.aperture_fstop = 3.5; cam3.data.dof.focus_distance = 22

# 4. CAM_entrance — eye-level
bpy.ops.object.camera_add(location=(0, -38, 4))
cam4 = bpy.context.active_object; cam4.name = "CAM_entrance"
cam4.data.lens = 24; cam4.data.sensor_width = 36; cam4.data.clip_end = 500
cam4.rotation_euler = (math.radians(88), 0, 0)

# 5. CAM_greenhouse_detail — 85mm close-up
bpy.ops.object.camera_add(location=(15, 18, 4))
cam5 = bpy.context.active_object; cam5.name = "CAM_greenhouse_detail"
cam5.data.lens = 85; cam5.data.sensor_width = 36; cam5.data.clip_end = 500
cam5.data.dof.use_dof = True; cam5.data.dof.aperture_fstop = 2.0
dx, dy, dz = 0 - 15, 25 - 18, 3 - 4
cam5.data.dof.focus_distance = math.sqrt(dx**2 + dy**2 + dz**2)
cam5.rotation_euler = (math.radians(85), 0, math.radians(-65))

# 6. CAM_firepit_evening — fire pit with string lights
bpy.ops.object.camera_add(location=(-30, -30, 3))
cam6 = bpy.context.active_object; cam6.name = "CAM_firepit_evening"
cam6.data.lens = 35; cam6.data.sensor_width = 36; cam6.data.clip_end = 500
cam6.rotation_euler = (math.radians(75), 0, math.radians(45))

# 7. CAM_coffee_bar — close-up
bpy.ops.object.camera_add(location=(-35, -8, 3))
cam7 = bpy.context.active_object; cam7.name = "CAM_coffee_bar"
cam7.data.lens = 50; cam7.data.sensor_width = 36; cam7.data.clip_end = 500
cam7.data.dof.use_dof = True; cam7.data.dof.aperture_fstop = 2.8
dx, dy, dz = -30 - (-35), -4 - (-8), 1.5 - 3
cam7.data.dof.focus_distance = math.sqrt(dx**2 + dy**2 + dz**2)
cam7.rotation_euler = (math.radians(78), 0, math.radians(-39))

# 8. CAM_spa_detail — v11: close-up of SQUARE saunas + hot tubs
bpy.ops.object.camera_add(location=(28, -35, 4))
cam8 = bpy.context.active_object; cam8.name = "CAM_spa_detail"
cam8.data.lens = 50; cam8.data.sensor_width = 36; cam8.data.clip_end = 500
cam8.data.dof.use_dof = True; cam8.data.dof.aperture_fstop = 2.8
dx, dy, dz = SX - 28, SY - (-35), 1.2 - 4
cam8.data.dof.focus_distance = math.sqrt(dx**2 + dy**2 + dz**2)
cam8.rotation_euler = (math.radians(76), 0, math.radians(140))

scene.camera = cam2

print("  Done: 8 cameras configured")

# ═══════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════
RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v11")
os.makedirs(RENDER_DIR, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'

build_time = time.time() - build_start
print(f"\nScene built in {build_time:.1f}s")
print(f"Total objects: {len(bpy.data.objects)}")
print("")
print("=" * 60)
print("  STARTING RENDERS — 8 cameras at 2K / 2048spp")
print("  Estimated time: 4-6 hours on Mac mini M4 GPU")
print("=" * 60)

cam_names = [
    'CAM_aerial', 'CAM_hero', 'CAM_pool_spa', 'CAM_entrance',
    'CAM_greenhouse_detail', 'CAM_firepit_evening', 'CAM_coffee_bar', 'CAM_spa_detail',
]

for ci, cam_name in enumerate(cam_names):
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        print(f"  WARNING: {cam_name} not found, skipping")
        continue
    scene.camera = cam_obj
    out_path = os.path.join(RENDER_DIR, f"v11_{cam_name}.png")
    scene.render.filepath = out_path
    render_start = time.time()
    print(f"\n  [{ci+1}/{len(cam_names)}] Rendering {cam_name}...")
    bpy.ops.render.render(write_still=True)
    render_time = time.time() - render_start
    print(f"  Saved: {out_path} ({render_time:.0f}s)")

save_path = os.path.expanduser("~/Projects/sponic-garden-3d/sponic-garden-v11.blend")
bpy.ops.wm.save_as_mainfile(filepath=save_path)

total_time = time.time() - build_start
print(f"\n{'=' * 60}")
print(f"  v11 COMPLETE — Total time: {total_time/60:.1f} minutes")
print(f"  Blend file: {save_path}")
print(f"  Renders: {RENDER_DIR}/")
print(f"{'=' * 60}")
