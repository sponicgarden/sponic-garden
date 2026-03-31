"""
Sponic Garden — v8 Polished
Fixes from v7: organic trees (icosphere), cone umbrellas, better cameras,
warm string lights, improved pool/spa detail, stepping stones, pergola accents.

Usage: blender --background --python build_v8_polished.py
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector

random.seed(42)  # reproducible randomness

# ═══════════════════════════════════════════
# CLEAN SCENE
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
    'pool': col("Pool_Area"),
    'spa': col("Spa_Wellness"),
    'landscape': col("Landscape"),
    'furniture': col("Furniture"),
    'lighting_deco': col("Deco_Lights"),
    'paths': col("Paths"),
    'tech': col("Tech"),
}

# ═══════════════════════════════════════════
# PBR MATERIALS
# ═══════════════════════════════════════════

def pbr(name, color, roughness, metallic=0.0, alpha=1.0, emission=0.0, emit_color=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = roughness
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
    noise.inputs['Detail'].default_value = 8.0
    noise.inputs['Roughness'].default_value = 0.6

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

MAT = {
    'steel':       pbr_tex("Steel",     (0.28,0.28,0.30), (0.35,0.35,0.38), 0.30, 15, metallic=0.85),
    'concrete':    pbr_tex("Concrete",  (0.50,0.48,0.44), (0.58,0.54,0.50), 0.92, 12),
    'concrete_lt': pbr_tex("Concrete_Lt",(0.62,0.60,0.56),(0.68,0.65,0.60), 0.88, 10),
    'cedar':       pbr_tex("Cedar",     (0.45,0.30,0.15), (0.55,0.38,0.20), 0.70, 25),
    'cedar_lt':    pbr_tex("Cedar_Lt",  (0.58,0.42,0.24), (0.65,0.48,0.28), 0.65, 25),
    'cedar_dk':    pbr_tex("Cedar_Dk",  (0.32,0.22,0.12), (0.40,0.28,0.15), 0.72, 25),
    'glass':       pbr("Glass",         (0.85,0.95,0.92), 0.02, alpha=0.20),
    'glass_tint':  pbr("Glass_Tint",    (0.55,0.78,0.72), 0.05, alpha=0.35),
    'green_roof':  pbr_tex("Green_Roof",(0.16,0.30,0.10), (0.22,0.38,0.15), 0.88, 6),
    'slate_roof':  pbr_tex("Slate_Roof",(0.22,0.22,0.25), (0.28,0.28,0.30), 0.75, 20),
    'grass': None,
    'soil':        pbr_tex("Soil",      (0.25,0.16,0.08), (0.35,0.22,0.12), 0.92, 8),
    'gravel':      pbr_tex("Gravel",    (0.50,0.46,0.40), (0.60,0.55,0.48), 0.95, 20),
    'sand':        pbr_tex("Sand",      (0.72,0.65,0.52), (0.78,0.70,0.58), 0.90, 10),
    'water_pool':  pbr("Pool_Water",    (0.10,0.35,0.50), 0.01, alpha=0.65),
    'water_warm':  pbr("Warm_Water",    (0.12,0.30,0.42), 0.02, alpha=0.55),
    'water_cold':  pbr("Cold_Water",    (0.06,0.18,0.32), 0.01, alpha=0.50),
    'sauna_wd':    pbr_tex("Sauna_Wood",(0.52,0.36,0.18), (0.60,0.42,0.22), 0.58, 30),
    'deck':        pbr_tex("Deck",      (0.42,0.30,0.16), (0.50,0.36,0.20), 0.68, 30),
    'tile_pool':   pbr_tex("Tile_Pool", (0.65,0.68,0.70), (0.72,0.74,0.76), 0.60, 15),
    'tile_blue':   pbr_tex("Tile_Blue", (0.28,0.42,0.52), (0.33,0.48,0.58), 0.55, 15),
    'cushion':     pbr("Cushion",       (0.80,0.76,0.70), 0.85),
    'cushion_dk':  pbr("Cushion_Dk",    (0.28,0.30,0.26), 0.80),
    'fabric_wht':  pbr("Fabric_White",  (0.88,0.86,0.82), 0.85),
    'fabric_tan':  pbr("Fabric_Tan",    (0.72,0.62,0.48), 0.82),
    'screen':      pbr("Screen",        (0.04,0.04,0.05), 0.10, emission=3.0),
    'speaker':     pbr("Speaker",       (0.10,0.10,0.11), 0.70),
    'asphalt':     pbr_tex("Asphalt",   (0.18,0.18,0.20), (0.22,0.22,0.24), 0.95, 12),
    'track':       pbr_tex("Track",     (0.55,0.35,0.20), (0.62,0.40,0.25), 0.85, 8),
    'stone_path':  pbr_tex("StonePath", (0.45,0.42,0.38), (0.55,0.52,0.48), 0.88, 18),
    'stepping':    pbr_tex("Stepping",  (0.52,0.50,0.46), (0.60,0.58,0.54), 0.85, 20),
    'bark':        pbr_tex("Bark",      (0.22,0.15,0.08), (0.30,0.20,0.12), 0.92, 35),
    'foliage':     pbr_tex("Foliage",   (0.08,0.22,0.05), (0.15,0.32,0.10), 0.80, 5, bump_str=0.25),
    'foliage_lt':  pbr_tex("Foliage_Lt",(0.15,0.35,0.10), (0.22,0.42,0.15), 0.78, 5, bump_str=0.25),
    'hedge':       pbr_tex("Hedge",     (0.06,0.18,0.04), (0.12,0.25,0.08), 0.85, 4, bump_str=0.30),
    'flowers_red': pbr("Fl_Red",        (0.65,0.10,0.08), 0.75),
    'flowers_purp':pbr("Fl_Purp",       (0.40,0.15,0.50), 0.75),
    'flowers_yel': pbr("Fl_Yel",        (0.80,0.70,0.15), 0.75),
    'flowers_wht': pbr("Fl_Wht",        (0.90,0.88,0.82), 0.75),
    'lantern':     pbr("Lantern",       (1.0,0.85,0.55), 0.3, emission=8.0, emit_color=(1.0,0.85,0.55)),
    'lantern_post':pbr("Lantern_Post",  (0.15,0.15,0.16), 0.50, metallic=0.7),
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

def make_building_shell(name, cx, cy, w, d, h, wall_thick=0.20, roof_thick=0.15,
                        wall_mat=None, roof_mat=None, floor_mat=None, collection=None):
    wm = wall_mat or MAT['concrete']
    rm = roof_mat or MAT['slate_roof']
    fm = floor_mat or MAT['concrete']
    col_target = collection or C['buildings']
    wt = wall_thick
    rt = roof_thick
    ft = 0.20

    box(f"{name}_Floor", cx, cy, ft/2, w, d, ft, fm, col_target, 0.02)
    box(f"{name}_Wall_S", cx, cy - d/2 + wt/2, ft + h/2, w, wt, h, wm, col_target)
    box(f"{name}_Wall_N", cx, cy + d/2 - wt/2, ft + h/2, w, wt, h, wm, col_target)
    box(f"{name}_Wall_W", cx - w/2 + wt/2, cy, ft + h/2, wt, d - 2*wt, h, wm, col_target)
    box(f"{name}_Wall_E", cx + w/2 - wt/2, cy, ft + h/2, wt, d - 2*wt, h, wm, col_target)
    roof_z = ft + h + rt/2
    box(f"{name}_Roof", cx, cy, roof_z, w + 0.5, d + 0.5, rt, rm, col_target, 0.03)

    # Door
    box(f"{name}_Door", cx, cy - d/2 - 0.01, ft + 1.1, 1.2, 0.05, 2.2, MAT['cedar_dk'], col_target, 0.008)
    # Window strip
    win_h = min(1.2, h * 0.3)
    box(f"{name}_Win_E", cx + w/2 + 0.01, cy, ft + h*0.6, 0.02, d*0.6, win_h, MAT['glass_tint'], col_target, 0)
    box(f"{name}_Win_W", cx - w/2 - 0.01, cy, ft + h*0.6, 0.02, d*0.5, win_h, MAT['glass_tint'], col_target, 0)


def make_glass_building(name, cx, cy, w, d, h, collection=None):
    col_target = collection or C['buildings']
    ft = 0.20
    fs = 0.10

    box(f"{name}_Floor", cx, cy, ft/2, w, d, ft, MAT['concrete'], col_target, 0.02)

    col_positions = [
        (-w/2, -d/2), (-w/2, 0), (-w/2, d/2),
        (w/2, -d/2), (w/2, 0), (w/2, d/2),
        (0, -d/2), (0, d/2),
    ]
    for i, (dx, dy) in enumerate(col_positions):
        box(f"{name}_Col_{i}", cx+dx, cy+dy, ft + h/2, fs, fs, h, MAT['steel'], col_target, 0.008)

    # Horizontal mullions
    for dy_pos in [-d/2, d/2]:
        box(f"{name}_Mul_NS_{dy_pos}", cx, cy+dy_pos, ft + h*0.5, w, fs, fs, MAT['steel'], col_target, 0.005)
    for dx_pos in [-w/2, w/2]:
        box(f"{name}_Mul_EW_{dx_pos}", cx+dx_pos, cy, ft + h*0.5, fs, d, fs, MAT['steel'], col_target, 0.005)

    for side, loc, dims in [
        ('S', (cx, cy - d/2, ft + h/2), (w, 0.02, h)),
        ('N', (cx, cy + d/2, ft + h/2), (w, 0.02, h)),
        ('W', (cx - w/2, cy, ft + h/2), (0.02, d, h)),
        ('E', (cx + w/2, cy, ft + h/2), (0.02, d, h)),
    ]:
        box(f"{name}_Glass_{side}", *loc, *dims, MAT['glass_tint'], col_target, 0)

    box(f"{name}_Roof", cx, cy, ft + h + 0.02, w, d, 0.04, MAT['glass_tint'], col_target, 0)
    for dx in [-w/4, 0, w/4]:
        box(f"{name}_RBeam_{dx}", cx+dx, cy, ft + h + 0.05, fs, d, fs, MAT['steel'], col_target, 0.005)


def make_organic_tree(name, cx, cy, collection=None, height=3.5, canopy_r=2.0):
    """Tree with icosphere canopy + vertex displacement for organic look"""
    col_target = collection or C['landscape']
    trunk_r = 0.08 + canopy_r * 0.05

    # Trunk — slight taper via cone
    bpy.ops.mesh.primitive_cone_add(radius1=trunk_r*1.3, radius2=trunk_r*0.6,
                                     depth=height, location=(cx, cy, height/2))
    trunk = bpy.context.active_object
    trunk.name = f"{name}_Trunk"
    bpy.ops.object.shade_smooth()
    trunk.data.materials.append(MAT['bark'])
    link_to(trunk, col_target)

    # Canopy clusters — icospheres with displacement for organic shape
    canopy_defs = [
        (0, 0, height + canopy_r*0.4, canopy_r, 'foliage'),
        (-canopy_r*0.35, canopy_r*0.2, height + canopy_r*0.8, canopy_r*0.65, 'foliage_lt'),
        (canopy_r*0.3, -canopy_r*0.15, height + canopy_r*0.6, canopy_r*0.75, 'foliage'),
        (0, -canopy_r*0.25, height + canopy_r*0.95, canopy_r*0.5, 'foliage_lt'),
    ]
    for i, (dx, dy, dz, r, mat_key) in enumerate(canopy_defs):
        bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=3,
                                               location=(cx+dx, cy+dy, dz))
        leaf = bpy.context.active_object
        leaf.name = f"{name}_Canopy_{i}"

        # Randomize vertices for organic shape
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(leaf.data)
        for v in bm.verts:
            v.co.x += random.uniform(-r*0.12, r*0.12)
            v.co.y += random.uniform(-r*0.12, r*0.12)
            v.co.z += random.uniform(-r*0.08, r*0.08)
        bmesh.update_edit_mesh(leaf.data)
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.shade_smooth()
        leaf.data.materials.append(MAT[mat_key])
        link_to(leaf, col_target)


def make_hedge(name, cx, cy, length, width=0.8, height=1.2, along_x=True, coll=None):
    coll = coll or C['landscape']
    if along_x:
        box(f"{name}", cx, cy, height/2, length, width, height, MAT['hedge'], coll, 0.06)
    else:
        box(f"{name}", cx, cy, height/2, width, length, height, MAT['hedge'], coll, 0.06)


def make_shrub(name, cx, cy, radius=0.6, coll=None):
    coll = coll or C['landscape']
    bpy.ops.mesh.primitive_ico_sphere_add(radius=radius, subdivisions=2,
                                           location=(cx, cy, radius*0.65))
    s = bpy.context.active_object
    s.name = name
    s.scale[2] = 0.65
    bpy.ops.object.transform_apply(scale=True)

    # Randomize
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(s.data)
    for v in bm.verts:
        v.co.x += random.uniform(-radius*0.1, radius*0.1)
        v.co.y += random.uniform(-radius*0.1, radius*0.1)
        v.co.z += random.uniform(-radius*0.06, radius*0.06)
    bmesh.update_edit_mesh(s.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.shade_smooth()
    s.data.materials.append(MAT['hedge'])
    link_to(s, coll)


def make_bench(name, cx, cy, angle=0, coll=None):
    coll = coll or C['furniture']
    box(f"{name}_Seat", cx, cy, 0.45, 1.5, 0.45, 0.06, MAT['cedar_lt'], coll, 0.005)
    box(f"{name}_Back", cx, cy - 0.18, 0.7, 1.5, 0.06, 0.5, MAT['cedar_lt'], coll, 0.005)
    for dx in [-0.6, 0.6]:
        for dy in [-0.15, 0.15]:
            box(f"{name}_L_{dx}_{dy}", cx+dx, cy+dy, 0.22, 0.05, 0.05, 0.44, MAT['steel'], coll, 0.003)
    if angle != 0:
        for obj in list(bpy.data.objects):
            if obj.name.startswith(name):
                obj.rotation_euler[2] = math.radians(angle)


def make_lounge(name, cx, cy, angle=0, coll=None):
    coll = coll or C['furniture']
    box(f"{name}_Fr", cx, cy, 0.28, 0.65, 1.8, 0.05, MAT['steel'], coll, 0.005)
    box(f"{name}_Cu", cx, cy+0.1, 0.34, 0.58, 1.5, 0.08, MAT['cushion'], coll, 0.008)
    box(f"{name}_Hd", cx, cy-0.7, 0.43, 0.58, 0.4, 0.06, MAT['cushion'], coll, 0.008)
    for dx in [-0.25, 0.25]:
        for dy in [-0.7, 0.7]:
            box(f"{name}_Lg_{dx}_{dy}", cx+dx, cy+dy, 0.13, 0.03, 0.03, 0.26, MAT['steel'], coll, 0.002)
    if angle != 0:
        for obj in list(bpy.data.objects):
            if obj.name.startswith(name):
                obj.rotation_euler[2] = math.radians(angle)


def make_umbrella(name, cx, cy, coll=None):
    """Cone-shaped umbrella instead of flat disc"""
    coll = coll or C['furniture']
    cyl(f"{name}_Pole", cx, cy, 1.4, 0.03, 2.8, MAT['lantern_post'], coll)
    bpy.ops.mesh.primitive_cone_add(radius1=1.6, radius2=0.0, depth=0.6,
                                     location=(cx, cy, 2.85))
    umb = bpy.context.active_object
    umb.name = f"{name}_Top"
    # Flip cone so wide part is up
    umb.rotation_euler[0] = math.radians(180)
    bpy.ops.object.transform_apply(rotation=True)
    bpy.ops.object.shade_smooth()
    umb.data.materials.append(MAT['fabric_tan'])
    link_to(umb, coll)


def make_table(name, cx, cy, coll=None):
    coll = coll or C['furniture']
    cyl(f"{name}_Top", cx, cy, 0.72, 0.5, 0.04, MAT['cedar_lt'], coll)
    cyl(f"{name}_Stem", cx, cy, 0.38, 0.05, 0.72, MAT['steel'], coll)
    cyl(f"{name}_Base", cx, cy, 0.03, 0.22, 0.04, MAT['steel'], coll)


def make_chair(name, cx, cy, coll=None):
    coll = coll or C['furniture']
    box(f"{name}_Se", cx, cy, 0.42, 0.48, 0.48, 0.05, MAT['cushion_dk'], coll, 0.005)
    box(f"{name}_Bk", cx, cy-0.22, 0.62, 0.48, 0.05, 0.35, MAT['cushion_dk'], coll, 0.005)
    for dx, dy in [(-0.18,-0.18),(0.18,-0.18),(-0.18,0.18),(0.18,0.18)]:
        box(f"{name}_L_{dx}_{dy}", cx+dx, cy+dy, 0.20, 0.035, 0.035, 0.40, MAT['steel'], coll, 0.002)


def make_lantern(name, cx, cy, coll=None):
    """Garden lantern — warm light sphere on post"""
    coll = coll or C['lighting_deco']
    cyl(f"{name}_Post", cx, cy, 1.1, 0.025, 2.2, MAT['lantern_post'], coll)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(cx, cy, 2.3))
    bulb = bpy.context.active_object
    bulb.name = f"{name}_Bulb"
    bpy.ops.object.shade_smooth()
    bulb.data.materials.append(MAT['lantern'])
    link_to(bulb, coll)

    # Actual point light for warm glow
    bpy.ops.object.light_add(type='POINT', location=(cx, cy, 2.3))
    light = bpy.context.active_object
    light.name = f"{name}_Light"
    light.data.energy = 15.0
    light.data.color = (1.0, 0.85, 0.55)
    light.data.shadow_soft_size = 0.3
    link_to(light, coll)


def make_walkway(name, x1, y1, x2, y2, collection=None):
    col_target = collection or C['paths']
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
    link_to(path, col_target)

    # Pergola-style slat roof
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, post_h + 0.06))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof"
    roof.dimensions = (length, 2.8, 0.06)
    roof.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    roof.data.materials.append(MAT['cedar'])
    link_to(roof, col_target)

    for t in [0.12, 0.5, 0.88]:
        px = x1 + dx*t
        py = y1 + dy*t
        for offset in [-1.0, 1.0]:
            ox = -math.sin(angle) * offset
            oy = math.cos(angle) * offset
            box(f"{name}_Post_{t}_{offset}", px+ox, py+oy, post_h/2, 0.12, 0.12, post_h, MAT['cedar'], col_target, 0.008)


# ═══════════════════════════════════════════
# SITE GROUND
# ═══════════════════════════════════════════
print("[1/11] Creating site...")

bpy.ops.mesh.primitive_plane_add(size=250, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"

mat_grass = bpy.data.materials.new("Ground_Grass")
mat_grass.use_nodes = True
nt = mat_grass.node_tree
nodes = nt.nodes
for n in nodes:
    nodes.remove(n)

out = nodes.new('ShaderNodeOutputMaterial')
bsdf = nodes.new('ShaderNodeBsdfPrincipled')

noise1 = nodes.new('ShaderNodeTexNoise')
noise1.inputs['Scale'].default_value = 30.0
noise1.inputs['Detail'].default_value = 14.0
noise1.inputs['Roughness'].default_value = 0.7

noise2 = nodes.new('ShaderNodeTexNoise')
noise2.inputs['Scale'].default_value = 4.0
noise2.inputs['Detail'].default_value = 6.0

mix = nodes.new('ShaderNodeMixRGB')
mix.blend_type = 'OVERLAY'
mix.inputs['Fac'].default_value = 0.25

ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.04, 0.10, 0.02, 1)
ramp.color_ramp.elements[1].color = (0.10, 0.24, 0.05, 1)

ramp2 = nodes.new('ShaderNodeValToRGB')
ramp2.color_ramp.elements[0].color = (0.07, 0.16, 0.03, 1)
ramp2.color_ramp.elements[1].color = (0.14, 0.30, 0.07, 1)

nt.links.new(noise1.outputs['Fac'], ramp.inputs['Fac'])
nt.links.new(noise2.outputs['Fac'], ramp2.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], mix.inputs['Color1'])
nt.links.new(ramp2.outputs['Color'], mix.inputs['Color2'])
nt.links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.90

bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.25
nt.links.new(noise1.outputs['Fac'], bump.inputs['Height'])
nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

ground.data.materials.append(mat_grass)
MAT['grass'] = mat_grass
link_to(ground, C['site'])
print("  Done")

# ═══════════════════════════════════════════
# BUILDINGS
# ═══════════════════════════════════════════
print("[2/11] Buildings...")

make_building_shell("Welcome", 0, -18, 10, 8, 4.5,
    wall_mat=MAT['concrete'], roof_mat=MAT['green_roof'])

make_glass_building("Greenhouse", 0, 25, 20, 15, 5.5)

make_building_shell("Dining", -22, 8, 15, 10, 4.5,
    wall_mat=MAT['cedar'], roof_mat=MAT['green_roof'])

make_building_shell("Education", 22, 10, 10, 10, 4.5,
    wall_mat=MAT['concrete_lt'], roof_mat=MAT['slate_roof'])

make_building_shell("Maker", -22, -8, 10, 10, 5.0,
    wall_mat=MAT['steel'], roof_mat=MAT['slate_roof'])

make_glass_building("Movement", 22, -8, 12, 10, 4.5)

make_building_shell("SpaHouse", 12, -28, 10, 10, 3.8,
    wall_mat=MAT['cedar'], roof_mat=MAT['green_roof'])

# Coffee bar
box("Coffee_Floor", -30, -4, 0.1, 6, 5, 0.2, MAT['concrete'], C['buildings'], 0.02)
box("Coffee_Roof", -30, -4, 3.15, 7, 6, 0.08, MAT['cedar'], C['buildings'], 0.02)
for dx, dy in [(-3,-2.5),(3,-2.5),(-3,2.5),(3,2.5)]:
    box(f"Coffee_Post_{dx}_{dy}", -30+dx, -4+dy, 1.55, 0.12, 0.12, 3.1, MAT['cedar'], C['buildings'])
box("Coffee_Counter", -30, -3, 0.55, 4, 0.6, 0.9, MAT['cedar_lt'], C['buildings'])

for dx in [-1.2, 0, 1.2]:
    cyl(f"Stool_{dx}", -30+dx, -3.8, 0.35, 0.16, 0.04, MAT['cushion_dk'], C['furniture'])
    cyl(f"Stool_L_{dx}", -30+dx, -3.8, 0.17, 0.025, 0.34, MAT['steel'], C['furniture'])

print("  Done: 7 buildings + coffee bar")

# ═══════════════════════════════════════════
# SWIMMING POOL
# ═══════════════════════════════════════════
print("[3/11] Pool...")

PX, PY = -8, -32

# Pool deck — warm sandstone tone
box("Pool_Deck", PX, PY, 0.08, 22, 14, 0.16, MAT['sand'], C['pool'], 0.02)

# Pool basin
box("Pool_Shell", PX-2, PY, -0.3, 14, 8, 1.5, MAT['tile_blue'], C['pool'], 0.03)

# Pool water
bpy.ops.mesh.primitive_plane_add(size=1, location=(PX-2, PY, 0.05))
pw = bpy.context.active_object
pw.name = "Pool_Water"
pw.dimensions = (13.6, 7.6, 0)
bpy.ops.object.transform_apply(scale=True)
pw.data.materials.append(MAT['water_pool'])
link_to(pw, C['pool'])

# Pool edge coping — stone
for loc, dims in [
    ((PX-2, PY-4.2, 0.14), (14.4, 0.45, 0.14)),
    ((PX-2, PY+4.2, 0.14), (14.4, 0.45, 0.14)),
    ((PX-9.2, PY, 0.14), (0.45, 8.4, 0.14)),
    ((PX+5.2, PY, 0.14), (0.45, 8.4, 0.14)),
]:
    box("Pool_Coping", *loc, *dims, MAT['stepping'], C['pool'], 0.012)

# Pool steps (shallow end)
for i in range(3):
    step_y = PY + 4.0 - i * 0.3
    step_z = 0.02 - i * 0.25
    box(f"Pool_Step_{i}", PX + 4, step_y, step_z, 3, 0.5, 0.15, MAT['tile_pool'], C['pool'], 0.01)

# Lounges (6)
for i in range(6):
    make_lounge(f"Lng_{i}", PX-7 + i*2.5, PY+5.8, coll=C['pool'])

# Umbrellas (3 cone-shaped)
for i, ux in enumerate([PX-5, PX-0.5, PX+4]):
    make_umbrella(f"Umb_{i}", ux, PY+5.8, coll=C['pool'])

# Side tables
for i, tx in enumerate([PX-4.5, PX+0.5]):
    make_table(f"Pool_Tbl_{i}", tx, PY+5.8, coll=C['pool'])

print("  Done: pool + lounges + umbrellas")

# ═══════════════════════════════════════════
# SPA & WELLNESS
# ═══════════════════════════════════════════
print("[4/11] Spa...")

SX, SY = 22, -28

# Spa deck
box("Spa_Deck", SX, SY, 0.08, 16, 12, 0.16, MAT['deck'], C['spa'], 0.02)

# Barrel sauna
o = cyl("Sauna_Barrel", SX-3, SY+2, 1.2, 1.2, 2.8, MAT['sauna_wd'], C['spa'])
o.rotation_euler[1] = math.radians(90)
bpy.ops.object.transform_apply(rotation=True)

cyl("Sauna_End", SX-3-1.4, SY+2, 1.2, 1.18, 0.08, MAT['cedar_dk'], C['spa'])
bpy.data.objects["Sauna_End"].rotation_euler[1] = math.radians(90)
cyl("Sauna_Chimney", SX-3, SY+2, 2.6, 0.08, 0.5, MAT['steel'], C['spa'])

# Cold plunge
cp = box("CPlunge_Shell", SX+2, SY+2, 0.2, 3.0, 2.0, 1.2, MAT['concrete'], C['spa'], 0.02)
cp.modifiers.new('Solidify', 'SOLIDIFY')
cp.modifiers['Solidify'].thickness = 0.1
cp.modifiers['Solidify'].offset = -1

bpy.ops.mesh.primitive_plane_add(size=1, location=(SX+2, SY+2, 0.7))
cpw = bpy.context.active_object
cpw.name = "CPlunge_Water"
cpw.dimensions = (2.8, 1.8, 0)
bpy.ops.object.transform_apply(scale=True)
cpw.data.materials.append(MAT['water_cold'])
link_to(cpw, C['spa'])

# Hot tubs (2)
for i, (hx, hy) in enumerate([(SX-3, SY-3), (SX+2, SY-3)]):
    ht = cyl(f"HotTub_{i}", hx, hy, 0.55, 1.2, 0.9, MAT['cedar_lt'], C['spa'])
    bpy.ops.object.modifier_add(type='SOLIDIFY')
    ht.modifiers['Solidify'].thickness = 0.10
    ht.modifiers['Solidify'].offset = -1
    bpy.ops.object.modifier_add(type='BEVEL')
    ht.modifiers['Bevel'].width = 0.015
    ht.modifiers['Bevel'].segments = 3
    cyl(f"HotTub_{i}_W", hx, hy, 0.85, 1.05, 0.02, MAT['water_warm'], C['spa'])

# Spa benches
make_bench("SpaBench_1", SX-0.5, SY-5.5, coll=C['spa'])
make_bench("SpaBench_2", SX+5.5, SY, angle=90, coll=C['spa'])
box("Towel_Rack", SX+6, SY+3, 1.0, 0.8, 0.3, 1.6, MAT['cedar'], C['spa'], 0.008)

print("  Done: barrel sauna, cold plunge, 2 hot tubs")

# ═══════════════════════════════════════════
# LANDSCAPE
# ═══════════════════════════════════════════
print("[5/11] Landscape...")

# Garden beds (NW)
for row in range(4):
    for ci in range(6):
        x = -38 + ci*3.8
        y = 20 + row*3.5
        box(f"Bed_{row}_{ci}", x, y, 0.25, 3.0, 1.2, 0.5, MAT['cedar_lt'], C['landscape'])
        box(f"Soil_{row}_{ci}", x, y, 0.48, 2.9, 1.1, 0.04, MAT['soil'], C['landscape'], 0)
        # Tiny plant indicators
        if (row + ci) % 3 == 0:
            bpy.ops.mesh.primitive_ico_sphere_add(radius=0.15, subdivisions=1, location=(x, y, 0.55))
            pl = bpy.context.active_object
            pl.name = f"Plant_{row}_{ci}"
            pl.scale[2] = 0.5
            bpy.ops.object.transform_apply(scale=True)
            pl.data.materials.append(MAT['foliage'])
            link_to(pl, C['landscape'])

# Orchard (NE) — organic trees
for i in range(12):
    tx = 28 + (i%4)*5
    ty = 22 + (i//4)*5
    make_organic_tree(f"Orch_{i}", tx, ty, height=3.5 + random.uniform(0,1))

# Scattered decorative trees
tree_spots = [
    (-35,-15),(-35,15),(35,15),(-12,-40),(14,-40),
    (-38,0),(38,0),(-15,38),(15,38),(-28,-22),(28,28),
    (-40,-25),(40,10),(-8,40),(8,40),(-25,32),(25,-18),
]
for i, (tx, ty) in enumerate(tree_spots):
    make_organic_tree(f"Deco_{i}", tx, ty,
                       height=2.5+random.uniform(0,1.5),
                       canopy_r=1.2+random.uniform(0,0.8))

# Hedges
make_hedge("H_EntryW", -4, -15, 6, along_x=False)
make_hedge("H_EntryE", 4, -15, 6, along_x=False)
make_hedge("H_PoolN", PX, PY+7.5, 22, height=1.0)
make_hedge("H_PoolS", PX, PY-7.5, 22, height=1.0)
make_hedge("H_SpaN", SX, SY+6.5, 16, height=1.0)
make_hedge("H_GardenS", -19, 18, 24, height=0.9)
make_hedge("H_GardenN", -19, 35, 24, height=0.9)

# Shrubs at entrances
shrub_spots = [
    (-3,-14),(3,-14),(-14,3),(-14,13),(17,5),(17,15),
    (-17,-3),(-17,-13),(16,-3),(16,-13),
    (-33,-7),(-27,-7),(-33,-1),(-27,-1),  # coffee area
]
for sx, sy in shrub_spots:
    make_shrub(f"Shrub_{sx}_{sy}", sx, sy, radius=0.4+random.uniform(0,0.2))

# Flower clusters along central paths
flower_mats = [MAT['flowers_red'], MAT['flowers_purp'], MAT['flowers_yel'], MAT['flowers_wht']]
for i in range(24):
    a = math.radians(i * 15)
    r = 7 + random.uniform(-0.5, 0.5)
    fx, fy = math.cos(a)*r, math.sin(a)*r
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.25, subdivisions=1, location=(fx, fy, 0.12))
    fl = bpy.context.active_object
    fl.name = f"Flower_{i}"
    fl.scale[2] = 0.4
    bpy.ops.object.transform_apply(scale=True)
    fl.data.materials.append(flower_mats[i % 4])
    link_to(fl, C['landscape'])

# Fire pit (SW)
cyl("FirePit", -24, -24, 0.25, 0.7, 0.5, MAT['concrete'], C['landscape'])
cyl("FireGlow", -24, -24, 0.45, 0.35, 0.08, MAT['lantern'], C['landscape'])

bpy.ops.mesh.primitive_torus_add(major_radius=2.5, minor_radius=0.28, location=(-24, -24, 0.48))
seat = bpy.context.active_object
seat.name = "FireSeat"
seat.data.materials.append(MAT['cedar'])
link_to(seat, C['landscape'])

for i in range(6):
    fa = math.radians(i*60+15)
    make_chair(f"FireCh_{i}", -24+math.cos(fa)*3.5, -24+math.sin(fa)*3.5, coll=C['landscape'])

# Central fountain
fount = cyl("Fountain", 0, 0, 0.3, 2.5, 0.6, MAT['concrete'], C['landscape'])
fount.modifiers.new('Solidify','SOLIDIFY')
fount.modifiers['Solidify'].thickness = 0.15
fount.modifiers['Solidify'].offset = -1
cyl("FountWater", 0, 0, 0.45, 2.3, 0.02, MAT['water_pool'], C['landscape'])
cyl("FountJet", 0, 0, 0.8, 0.06, 0.7, MAT['concrete_lt'], C['landscape'])

# Reflecting pool
rp = box("ReflPool", 0, 38, 0.0, 14, 3, 0.5, MAT['concrete'], C['landscape'], 0.02)
rp.modifiers.new('Solidify','SOLIDIFY')
rp.modifiers['Solidify'].thickness = 0.1
rp.modifiers['Solidify'].offset = -1
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 38, 0.2))
rpw = bpy.context.active_object
rpw.name = "ReflWater"
rpw.dimensions = (13.6, 2.6, 0)
bpy.ops.object.transform_apply(scale=True)
rpw.data.materials.append(MAT['water_pool'])
link_to(rpw, C['landscape'])

print("  Done: gardens, 29 trees, hedges, shrubs, flowers, fire pit, fountain")

# ═══════════════════════════════════════════
# SEATING
# ═══════════════════════════════════════════
print("[6/11] Outdoor seating...")

# Dining patio
box("DiningPatio", -30, 14, 0.05, 8, 8, 0.1, MAT['stone_path'], C['furniture'], 0.01)
for i in range(4):
    tx = -32 + (i%2)*4
    ty = 12 + (i//2)*4
    make_table(f"DTbl_{i}", tx, ty, coll=C['furniture'])
    for j in range(4):
        ca = math.radians(j*90+45)
        make_chair(f"DCh_{i}_{j}", tx+math.cos(ca)*0.8, ty+math.sin(ca)*0.8, coll=C['furniture'])

# Garden benches
for i in range(3):
    make_bench(f"GBench_{i}", -38+i*10, 17, coll=C['furniture'])

# Courtyard benches
for i in range(4):
    ba = math.radians(i*90+45)
    make_bench(f"CBench_{i}", math.cos(ba)*5, math.sin(ba)*5, angle=i*90, coll=C['furniture'])

# Yoga deck
box("YogaDeck", 35, -5, 0.05, 12, 12, 0.1, MAT['deck'], C['furniture'], 0.01)
for row in range(3):
    for ci in range(3):
        box(f"YogaMat_{row}_{ci}", 32+ci*3, -8+row*3, 0.12, 1.8, 0.7, 0.03, MAT['cushion'], C['furniture'], 0.005)

print("  Done")

# ═══════════════════════════════════════════
# GARDEN LANTERNS (warm ambient)
# ═══════════════════════════════════════════
print("[7/11] Decorative lighting...")

lantern_spots = [
    # Along central paths
    (5, 0), (-5, 0), (0, 5), (0, -5),
    (3.5, 3.5), (-3.5, 3.5), (3.5, -3.5), (-3.5, -3.5),
    # Pool area
    (PX-10, PY), (PX+6, PY), (PX, PY+7), (PX, PY-7),
    # Spa area
    (SX-8, SY), (SX+8, SY),
    # Dining patio
    (-34, 14), (-26, 14),
    # Garden
    (-38, 17), (-18, 17),
    # Entrance
    (-6, -12), (6, -12),
    # Fire pit
    (-28, -24), (-20, -24),
]
for i, (lx, ly) in enumerate(lantern_spots):
    make_lantern(f"Lantern_{i}", lx, ly)

print("  Done: 22 garden lanterns")

# ═══════════════════════════════════════════
# WALKWAYS
# ═══════════════════════════════════════════
print("[8/11] Walkways...")

make_walkway("WK_WtoD", -4, -14, -15, 3)
make_walkway("WK_WtoM", -4, -15, -17, -4)
make_walkway("WK_WtoMv", 4, -14, 16, -5)
make_walkway("WK_WtoE", 4, -14, 17, 5)
make_walkway("WK_DtoGH", -15, 12, -8, 18)
make_walkway("WK_EtoGH", 17, 14, 9, 18)
make_walkway("WK_toPool", 4, -22, PX+8, PY+7)
make_walkway("WK_toSpa", 10, -22, SX-6, SY+6)

# Radial ground paths + stepping stones
for angle_deg in range(0, 360, 45):
    a = math.radians(angle_deg)
    x2 = math.cos(a)*14
    y2 = math.sin(a)*14
    length = math.sqrt(x2*x2+y2*y2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x2/2, y2/2, 0.025))
    rp = bpy.context.active_object
    rp.name = f"RadPath_{angle_deg}"
    rp.dimensions = (length, 1.6, 0.05)
    rp.rotation_euler = (0, 0, math.atan2(y2, x2))
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    rp.data.materials.append(MAT['stone_path'])
    link_to(rp, C['paths'])

# Stepping stones along key paths
for i in range(8):
    sx = -30 + i*3 + random.uniform(-0.3, 0.3)
    sy = -20 + random.uniform(-0.3, 0.3)
    cyl(f"Step_pool_{i}", sx, sy, 0.025, 0.3, 0.04, MAT['stepping'], C['paths'])

# Running circuit
S = 90.0
INSET = 5.0
for side, loc, dims in [
    ("S",(0,-S/2+INSET,0.03),(S-2*INSET,1.8,0.04)),
    ("N",(0,S/2-INSET,0.03),(S-2*INSET,1.8,0.04)),
    ("W",(-S/2+INSET,0,0.03),(1.8,S-2*INSET,0.04)),
    ("E",(S/2-INSET,0,0.03),(1.8,S-2*INSET,0.04)),
]:
    box(f"Circuit_{side}",*loc,*dims,MAT['track'],C['paths'],0.005)

print("  Done")

# ═══════════════════════════════════════════
# TECH
# ═══════════════════════════════════════════
print("[9/11] Tech...")

for i, (x,y,z) in enumerate([
    (-3,-18,3.5),(3,-18,3.5),(-5,22,4),(0,28,4),(5,22,4),
    (-25,8,3.5),(-19,8,3.5),(20,8,3.5),(24,12,3.5),
    (-24,-8,4),(-20,-8,4),(20,-10,3.5),(24,-6,3.5),
    (10,-28,3),(PX,PY+7,2),(0,0,2.5),(-24,-24,2),(35,-5,2),
]):
    box(f"Spk_{i}",x,y,z,0.18,0.18,0.25,MAT['speaker'],C['tech'],0.005)
print("  Done")

# ═══════════════════════════════════════════
# RENDER SETUP
# ═══════════════════════════════════════════
print("[10/11] Render settings...")

scene.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = 'GPU'
except:
    scene.cycles.device = 'CPU'

scene.cycles.samples = 2048
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.008
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.max_bounces = 16

scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except:
    try:
        scene.view_settings.look = 'AgX - Medium Contrast'
    except:
        pass
scene.view_settings.exposure = 0.5

scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# World: warm golden hour sky
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
for n in wn:
    wn.remove(n)

sky = wn.new('ShaderNodeTexSky')
sky.sky_type = 'HOSEK_WILKIE'
sky.sun_elevation = math.radians(25)   # lower = warmer golden hour
sky.sun_rotation = math.radians(-35)
try:
    sky.turbidity = 3.5
except:
    pass

bg = wn.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value = 1.3
out = wn.new('ShaderNodeOutputWorld')
wl.new(sky.outputs['Color'], bg.inputs['Color'])
wl.new(bg.outputs['Background'], out.inputs['Surface'])

# Key sun — warm
bpy.ops.object.light_add(type='SUN', location=(30, -30, 50))
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = 5.0
sun.data.color = (1.0, 0.95, 0.85)  # warm tint
sun.data.angle = math.radians(0.5)
sun.rotation_euler = (math.radians(25), math.radians(15), math.radians(-35))

# Fill from opposite
bpy.ops.object.light_add(type='SUN', location=(-20, 20, 40))
fill = bpy.context.active_object
fill.name = "Fill"
fill.data.energy = 1.0
fill.data.color = (0.85, 0.90, 1.0)  # cool fill for contrast
fill.data.angle = math.radians(3.0)
fill.rotation_euler = (math.radians(55), math.radians(-10), math.radians(150))

print("  Done: Cycles 2048spp + AgX + golden hour")

# ═══════════════════════════════════════════
# CAMERAS
# ═══════════════════════════════════════════
print("[11/11] Cameras...")

# Aerial
bpy.ops.object.camera_add(location=(0, 0, 85))
cam1 = bpy.context.active_object
cam1.name = "CAM_aerial"
cam1.data.type = 'ORTHO'
cam1.data.ortho_scale = 100

# Hero — lower, warmer angle
bpy.ops.object.camera_add(location=(48, -45, 25))
cam2 = bpy.context.active_object
cam2.name = "CAM_hero"
cam2.data.lens = 28
cam2.data.sensor_width = 36
cam2.data.clip_end = 500
cam2.rotation_euler = (math.radians(68), 0, math.radians(40))

# Pool + spa view — the money shot
bpy.ops.object.camera_add(location=(35, -55, 12))
cam3 = bpy.context.active_object
cam3.name = "CAM_pool_spa"
cam3.data.lens = 32
cam3.data.sensor_width = 36
cam3.data.clip_end = 500
cam3.rotation_euler = (math.radians(80), 0, math.radians(15))
cam3.data.dof.use_dof = True
cam3.data.dof.aperture_fstop = 4.0
cam3.data.dof.focus_distance = 25

# Entrance — human eye level, looking into campus
bpy.ops.object.camera_add(location=(0, -42, 4.5))
cam4 = bpy.context.active_object
cam4.name = "CAM_entrance"
cam4.data.lens = 24
cam4.data.sensor_width = 36
cam4.data.clip_end = 500
cam4.rotation_euler = (math.radians(88), 0, 0)

# Garden & courtyard detail
bpy.ops.object.camera_add(location=(-18, 10, 6))
cam5 = bpy.context.active_object
cam5.name = "CAM_garden"
cam5.data.lens = 50
cam5.data.sensor_width = 36
cam5.data.clip_end = 500
cam5.data.dof.use_dof = True
cam5.data.dof.aperture_fstop = 2.8
cam5.data.dof.focus_distance = 8
cam5.rotation_euler = (math.radians(75), 0, math.radians(-110))

scene.camera = cam2

# ═══════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════
RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v8")
os.makedirs(RENDER_DIR, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'

for cam_name in ['CAM_aerial', 'CAM_hero', 'CAM_pool_spa', 'CAM_entrance', 'CAM_garden']:
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        continue
    scene.camera = cam_obj
    out_path = os.path.join(RENDER_DIR, f"v8_{cam_name}.png")
    scene.render.filepath = out_path
    print(f"  Rendering {cam_name}...")
    bpy.ops.render.render(write_still=True)
    print(f"  Saved: {out_path}")

save_path = os.path.expanduser("~/Projects/sponic-garden-3d/sponic-garden-v8.blend")
bpy.ops.wm.save_as_mainfile(filepath=save_path)
print(f"\nDone! Saved to {save_path}")
