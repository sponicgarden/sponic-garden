"""
Sponic Garden — v7 Attractive
Major upgrade: swimming pool, barrel sauna, lounge seating, hedges, textured materials,
better lighting, and more inviting camera angles.

Usage: blender --background --python build_v7_attractive.py
"""
import bpy
import bmesh
import math
import os
from mathutils import Vector

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
    'paths': col("Paths"),
    'tech': col("Tech"),
}

# ═══════════════════════════════════════════
# PBR MATERIALS — with procedural texture
# ═══════════════════════════════════════════

def pbr(name, color, roughness, metallic=0.0, alpha=1.0, emission=0.0):
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
    return m

def pbr_textured(name, color1, color2, roughness, scale=8.0, metallic=0.0):
    """PBR material with noise texture variation for realism"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nodes = nt.nodes
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic

    # Noise texture for color variation
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 8.0
    noise.inputs['Roughness'].default_value = 0.6

    # Color ramp between two tones
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*color1, 1.0)
    ramp.color_ramp.elements[1].color = (*color2, 1.0)

    # Noise for roughness variation too
    mix_rough = nodes.new('ShaderNodeMath')
    mix_rough.operation = 'MULTIPLY'
    mix_rough.inputs[1].default_value = roughness

    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(noise.outputs['Fac'], mix_rough.inputs[0])
    nt.links.new(mix_rough.outputs['Value'], bsdf.inputs['Roughness'])

    # Bump from noise for surface texture
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.15
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return m

MAT = {
    # Structures
    'steel':        pbr_textured("Steel",     (0.28, 0.28, 0.30), (0.35, 0.35, 0.38), 0.30, 15.0, metallic=0.85),
    'concrete':     pbr_textured("Concrete",  (0.50, 0.48, 0.44), (0.58, 0.54, 0.50), 0.92, 12.0),
    'concrete_lt':  pbr_textured("Concrete_Lt",(0.62, 0.60, 0.56), (0.68, 0.65, 0.60), 0.88, 10.0),
    'cedar':        pbr_textured("Cedar",     (0.45, 0.30, 0.15), (0.55, 0.38, 0.20), 0.70, 25.0),
    'cedar_lt':     pbr_textured("Cedar_Lt",  (0.58, 0.42, 0.24), (0.65, 0.48, 0.28), 0.65, 25.0),
    'cedar_dark':   pbr_textured("Cedar_Dk",  (0.32, 0.22, 0.12), (0.40, 0.28, 0.15), 0.72, 25.0),

    # Glass
    'glass':        pbr("Glass",       (0.85, 0.95, 0.92), 0.02, alpha=0.20),
    'glass_tint':   pbr("Glass_Tint",  (0.55, 0.78, 0.72), 0.05, alpha=0.35),

    # Roof
    'green_roof':   pbr_textured("Green_Roof",(0.16, 0.30, 0.10), (0.22, 0.38, 0.15), 0.88, 6.0),
    'slate_roof':   pbr_textured("Slate_Roof",(0.22, 0.22, 0.25), (0.28, 0.28, 0.30), 0.75, 20.0),

    # Landscape
    'grass':        None,  # Created procedurally below
    'soil':         pbr_textured("Soil",      (0.25, 0.16, 0.08), (0.35, 0.22, 0.12), 0.92, 8.0),
    'gravel':       pbr_textured("Gravel",    (0.50, 0.46, 0.40), (0.60, 0.55, 0.48), 0.95, 20.0),
    'sand':         pbr_textured("Sand",      (0.72, 0.65, 0.52), (0.78, 0.70, 0.58), 0.90, 10.0),

    # Water
    'water_pool':   pbr("Pool_Water",  (0.10, 0.35, 0.50), 0.01, alpha=0.65),
    'water_warm':   pbr("Warm_Water",  (0.12, 0.30, 0.42), 0.02, alpha=0.60),
    'water_cold':   pbr("Cold_Water",  (0.08, 0.20, 0.35), 0.01, alpha=0.55),

    # Fixtures
    'sauna_wd':     pbr_textured("Sauna_Wood",(0.52, 0.36, 0.18), (0.60, 0.42, 0.22), 0.58, 30.0),
    'deck':         pbr_textured("Deck",      (0.42, 0.30, 0.16), (0.50, 0.36, 0.20), 0.68, 30.0),
    'tile_pool':    pbr_textured("Tile_Pool", (0.68, 0.72, 0.75), (0.75, 0.78, 0.80), 0.60, 15.0),
    'tile_blue':    pbr_textured("Tile_Blue", (0.30, 0.45, 0.55), (0.35, 0.50, 0.60), 0.55, 15.0),
    'cushion':      pbr("Cushion",     (0.82, 0.78, 0.72), 0.85),
    'cushion_dk':   pbr("Cushion_Dk",  (0.30, 0.32, 0.28), 0.80),
    'fabric':       pbr("Fabric",      (0.70, 0.68, 0.62), 0.90),

    # Tech
    'screen':       pbr("Screen",      (0.04, 0.04, 0.05), 0.10, emission=3.0),
    'speaker':      pbr("Speaker",     (0.10, 0.10, 0.11), 0.70),

    # Paths
    'asphalt':      pbr_textured("Asphalt",   (0.18, 0.18, 0.20), (0.22, 0.22, 0.24), 0.95, 12.0),
    'track':        pbr_textured("Track",     (0.55, 0.35, 0.20), (0.62, 0.40, 0.25), 0.85, 8.0),
    'stone_path':   pbr_textured("StonePath", (0.45, 0.42, 0.38), (0.55, 0.52, 0.48), 0.88, 18.0),

    # Trees
    'bark':         pbr_textured("Bark",      (0.22, 0.15, 0.08), (0.30, 0.20, 0.12), 0.92, 35.0),
    'foliage':      pbr_textured("Foliage",   (0.08, 0.22, 0.05), (0.15, 0.32, 0.10), 0.80, 5.0),
    'foliage_lt':   pbr_textured("Foliage_Lt",(0.15, 0.35, 0.10), (0.22, 0.42, 0.15), 0.78, 5.0),
    'hedge':        pbr_textured("Hedge",     (0.06, 0.18, 0.04), (0.12, 0.25, 0.08), 0.85, 4.0),
    'flowers_red':  pbr("Flowers_Red", (0.65, 0.10, 0.08), 0.75),
    'flowers_purp': pbr("Flowers_Purp",(0.40, 0.15, 0.50), 0.75),
    'flowers_yel':  pbr("Flowers_Yel", (0.80, 0.70, 0.15), 0.75),
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
                        wall_mat=None, roof_mat=None, floor_mat=None, collection=None,
                        has_door=True):
    wm = wall_mat or MAT['concrete']
    rm = roof_mat or MAT['slate_roof']
    fm = floor_mat or MAT['concrete']
    col_target = collection or C['buildings']
    wt = wall_thick
    rt = roof_thick
    ft = 0.20

    # Floor slab
    box(f"{name}_Floor", cx, cy, ft/2, w, d, ft, fm, col_target, 0.02)

    # 4 walls meeting at corners
    box(f"{name}_Wall_S", cx, cy - d/2 + wt/2, ft + h/2, w, wt, h, wm, col_target)
    box(f"{name}_Wall_N", cx, cy + d/2 - wt/2, ft + h/2, w, wt, h, wm, col_target)
    box(f"{name}_Wall_W", cx - w/2 + wt/2, cy, ft + h/2, wt, d - 2*wt, h, wm, col_target)
    box(f"{name}_Wall_E", cx + w/2 - wt/2, cy, ft + h/2, wt, d - 2*wt, h, wm, col_target)

    # Roof
    roof_z = ft + h + rt/2
    box(f"{name}_Roof", cx, cy, roof_z, w + 0.5, d + 0.5, rt, rm, col_target, 0.03)

    # Door indication (recessed panel on south wall)
    if has_door:
        box(f"{name}_Door", cx, cy - d/2 - 0.01, ft + 1.1, 1.2, 0.05, 2.2, MAT['cedar_dark'], col_target, 0.008)

    # Window strip (glass band on east wall)
    win_h = min(1.2, h * 0.3)
    win_z = ft + h * 0.6
    box(f"{name}_Window_E", cx + w/2 + 0.01, cy, win_z, 0.02, d * 0.6, win_h, MAT['glass_tint'], col_target, 0)


def make_glass_building(name, cx, cy, w, d, h, collection=None):
    col_target = collection or C['buildings']
    ft = 0.20
    fs = 0.10  # frame size

    box(f"{name}_Floor", cx, cy, ft/2, w, d, ft, MAT['concrete'], col_target, 0.02)

    # Steel frame columns
    col_positions = [
        (-w/2, -d/2), (-w/2, 0), (-w/2, d/2),
        (w/2, -d/2), (w/2, 0), (w/2, d/2),
        (0, -d/2), (0, d/2),
    ]
    for i, (dx, dy) in enumerate(col_positions):
        box(f"{name}_Col_{i}", cx+dx, cy+dy, ft + h/2, fs, fs, h, MAT['steel'], col_target, 0.008)

    # Horizontal mullions at mid-height
    for dy_pos in [-d/2, d/2]:
        box(f"{name}_Mullion_NS", cx, cy+dy_pos, ft + h/2, w, fs, fs, MAT['steel'], col_target, 0.005)
    for dx_pos in [-w/2, w/2]:
        box(f"{name}_Mullion_EW", cx+dx_pos, cy, ft + h/2, fs, d, fs, MAT['steel'], col_target, 0.005)

    # Glass panels
    for side, loc, dims in [
        ('S', (cx, cy - d/2, ft + h/2), (w, 0.02, h)),
        ('N', (cx, cy + d/2, ft + h/2), (w, 0.02, h)),
        ('W', (cx - w/2, cy, ft + h/2), (0.02, d, h)),
        ('E', (cx + w/2, cy, ft + h/2), (0.02, d, h)),
    ]:
        box(f"{name}_Glass_{side}", *loc, *dims, MAT['glass_tint'], col_target, 0)

    # Glass roof with ridge beams
    box(f"{name}_Roof", cx, cy, ft + h + 0.02, w, d, 0.04, MAT['glass_tint'], col_target, 0)
    for dx in [-w/4, 0, w/4]:
        box(f"{name}_Beam", cx+dx, cy, ft + h + 0.05, fs, d, fs, MAT['steel'], col_target, 0.005)


def make_tree(name, cx, cy, collection=None, height=3.0, canopy_r=1.8):
    col_target = collection or C['landscape']
    trunk_r = 0.10 + canopy_r * 0.04
    cyl(f"{name}_Trunk", cx, cy, height/2, trunk_r, height, MAT['bark'], col_target)

    for i, (dx, dy, dz, r) in enumerate([
        (0, 0, height + canopy_r*0.6, canopy_r),
        (-canopy_r*0.3, canopy_r*0.2, height + canopy_r*0.9, canopy_r*0.7),
        (canopy_r*0.25, -canopy_r*0.15, height + canopy_r*0.75, canopy_r*0.8),
    ]):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=16, ring_count=12,
                                              location=(cx+dx, cy+dy, dz))
        leaf = bpy.context.active_object
        leaf.name = f"{name}_Foliage_{i}"
        leaf.data.materials.append(MAT['foliage'] if i % 2 == 0 else MAT['foliage_lt'])
        bpy.ops.object.shade_smooth()
        link_to(leaf, col_target)


def make_hedge(name, cx, cy, length, width=0.8, height=1.2, along_x=True, coll=None):
    """Box hedge with rounded top"""
    coll = coll or C['landscape']
    if along_x:
        box(f"{name}_Base", cx, cy, height/2, length, width, height, MAT['hedge'], coll, 0.04)
    else:
        box(f"{name}_Base", cx, cy, height/2, width, length, height, MAT['hedge'], coll, 0.04)


def make_shrub(name, cx, cy, radius=0.6, coll=None):
    """Simple decorative shrub"""
    coll = coll or C['landscape']
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=12, ring_count=8,
                                          location=(cx, cy, radius * 0.7))
    s = bpy.context.active_object
    s.name = name
    s.scale[2] = 0.7  # flatten slightly
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    s.data.materials.append(MAT['hedge'])
    link_to(s, coll)


def make_bench(name, cx, cy, angle=0, coll=None):
    """Park bench: seat + backrest + legs"""
    coll = coll or C['furniture']
    # Seat
    box(f"{name}_Seat", cx, cy, 0.45, 1.5, 0.45, 0.06, MAT['cedar_lt'], coll, 0.005)
    # Backrest
    box(f"{name}_Back", cx, cy - 0.18, 0.7, 1.5, 0.06, 0.5, MAT['cedar_lt'], coll, 0.005)
    # Legs (4)
    for dx in [-0.6, 0.6]:
        for dy in [-0.15, 0.15]:
            box(f"{name}_Leg", cx+dx, cy+dy, 0.22, 0.06, 0.06, 0.44, MAT['steel'], coll, 0.003)

    # Apply rotation to all parts
    if angle != 0:
        for obj in bpy.data.objects:
            if obj.name.startswith(name):
                obj.rotation_euler[2] = math.radians(angle)


def make_lounge_chair(name, cx, cy, angle=0, coll=None):
    """Pool lounge chair"""
    coll = coll or C['furniture']
    # Frame
    box(f"{name}_Frame", cx, cy, 0.30, 0.65, 1.8, 0.06, MAT['steel'], coll, 0.005)
    # Cushion
    box(f"{name}_Cushion", cx, cy + 0.1, 0.36, 0.58, 1.5, 0.08, MAT['cushion'], coll, 0.008)
    # Head rest (angled)
    box(f"{name}_Head", cx, cy - 0.7, 0.45, 0.58, 0.4, 0.06, MAT['cushion'], coll, 0.008)
    # Legs
    for dx in [-0.25, 0.25]:
        for dy in [-0.7, 0.7]:
            box(f"{name}_Leg", cx+dx, cy+dy, 0.14, 0.04, 0.04, 0.28, MAT['steel'], coll, 0.002)

    if angle != 0:
        for obj in bpy.data.objects:
            if obj.name.startswith(name):
                obj.rotation_euler[2] = math.radians(angle)


def make_table(name, cx, cy, coll=None):
    """Round outdoor table"""
    coll = coll or C['furniture']
    cyl(f"{name}_Top", cx, cy, 0.72, 0.5, 0.04, MAT['cedar_lt'], coll)
    cyl(f"{name}_Stem", cx, cy, 0.38, 0.06, 0.72, MAT['steel'], coll)
    cyl(f"{name}_Base", cx, cy, 0.03, 0.25, 0.04, MAT['steel'], coll)


def make_chair(name, cx, cy, coll=None):
    """Simple outdoor chair"""
    coll = coll or C['furniture']
    box(f"{name}_Seat", cx, cy, 0.42, 0.5, 0.5, 0.05, MAT['cushion_dk'], coll, 0.005)
    box(f"{name}_Back", cx, cy - 0.22, 0.62, 0.5, 0.05, 0.35, MAT['cushion_dk'], coll, 0.005)
    for dx, dy in [(-0.2, -0.2), (0.2, -0.2), (-0.2, 0.2), (0.2, 0.2)]:
        box(f"{name}_Leg", cx+dx, cy+dy, 0.20, 0.04, 0.04, 0.40, MAT['steel'], coll, 0.002)


def make_walkway(name, x1, y1, x2, y2, collection=None):
    col_target = collection or C['paths']
    dx, dy = x2-x1, y2-y1
    length = math.sqrt(dx*dx + dy*dy)
    cx, cy = (x1+x2)/2, (y1+y2)/2
    angle = math.atan2(dy, dx)
    post_h = 3.0
    ft = 0.20

    # Ground path — stone-look
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, ft/2))
    path = bpy.context.active_object
    path.name = f"{name}_Path"
    path.dimensions = (length, 2.4, ft)
    path.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    path.data.materials.append(MAT['stone_path'])
    link_to(path, col_target)

    # Cedar slat roof
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, post_h + 0.06))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof"
    roof.dimensions = (length, 2.8, 0.08)
    roof.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    roof.data.materials.append(MAT['cedar'])
    link_to(roof, col_target)

    # Posts — cedar
    for t in [0.15, 0.5, 0.85]:
        px = x1 + dx*t
        py = y1 + dy*t
        for offset in [-1.0, 1.0]:
            ox = -math.sin(angle) * offset
            oy = math.cos(angle) * offset
            box(f"{name}_Post", px+ox, py+oy, post_h/2, 0.12, 0.12, post_h, MAT['cedar'], col_target, 0.008)


# ═══════════════════════════════════════════
# SITE: 90m x 90m
# ═══════════════════════════════════════════
print("[1/10] Creating site...")

# Procedural grass ground
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

# Two noise layers for natural grass variation
noise1 = nodes.new('ShaderNodeTexNoise')
noise1.inputs['Scale'].default_value = 25.0
noise1.inputs['Detail'].default_value = 12.0
noise1.inputs['Roughness'].default_value = 0.65

noise2 = nodes.new('ShaderNodeTexNoise')
noise2.inputs['Scale'].default_value = 3.0
noise2.inputs['Detail'].default_value = 6.0

mix = nodes.new('ShaderNodeMixRGB')
mix.blend_type = 'OVERLAY'
mix.inputs['Fac'].default_value = 0.3

ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.05, 0.12, 0.02, 1)  # dark grass
ramp.color_ramp.elements[1].color = (0.12, 0.28, 0.06, 1)  # lighter grass

ramp2 = nodes.new('ShaderNodeValToRGB')
ramp2.color_ramp.elements[0].color = (0.08, 0.18, 0.04, 1)
ramp2.color_ramp.elements[1].color = (0.16, 0.32, 0.08, 1)

nt.links.new(noise1.outputs['Fac'], ramp.inputs['Fac'])
nt.links.new(noise2.outputs['Fac'], ramp2.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], mix.inputs['Color1'])
nt.links.new(ramp2.outputs['Color'], mix.inputs['Color2'])
nt.links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.88

# Bump for grass texture
bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.2
nt.links.new(noise1.outputs['Fac'], bump.inputs['Height'])
nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
ground.data.materials.append(mat_grass)
MAT['grass'] = mat_grass
link_to(ground, C['site'])

print("  Done")

# ═══════════════════════════════════════════
# 7 BUILDINGS + COFFEE BAR
# ═══════════════════════════════════════════
print("[2/10] Building structures...")

# 1. Welcome Center (south entrance)
make_building_shell("Welcome", 0, -18, 10, 8, 4.5,
    wall_mat=MAT['concrete'], roof_mat=MAT['green_roof'], floor_mat=MAT['concrete'])

# 2. Greenhouse (north, glass)
make_glass_building("Greenhouse", 0, 25, 20, 15, 5.5)

# 3. Dining Hall (west)
make_building_shell("Dining", -22, 8, 15, 10, 4.5,
    wall_mat=MAT['cedar'], roof_mat=MAT['green_roof'])

# 4. Education Pavilion (east)
make_building_shell("Education", 22, 10, 10, 10, 4.5,
    wall_mat=MAT['concrete_lt'], roof_mat=MAT['slate_roof'])

# 5. Maker Studio (southwest)
make_building_shell("Maker", -22, -8, 10, 10, 5.0,
    wall_mat=MAT['steel'], roof_mat=MAT['slate_roof'])

# 6. Movement Studio (east, glass)
make_glass_building("Movement", 22, -8, 12, 10, 4.5)

# 7. Spa House (SE, near pool)
make_building_shell("Spa", 12, -28, 10, 10, 3.8,
    wall_mat=MAT['cedar'], roof_mat=MAT['green_roof'])

# 8. Coffee Bar (open pavilion SW, near dining)
box("Coffee_Floor", -30, -4, 0.1, 6, 5, 0.2, MAT['concrete'], C['buildings'], 0.02)
box("Coffee_Roof", -30, -4, 3.15, 7, 6, 0.10, MAT['cedar'], C['buildings'], 0.02)
for dx, dy in [(-3, -2.5), (3, -2.5), (-3, 2.5), (3, 2.5)]:
    box("Coffee_Post", -30+dx, -4+dy, 1.55, 0.12, 0.12, 3.1, MAT['cedar'], C['buildings'])
box("Coffee_Counter", -30, -3, 0.55, 4, 0.6, 0.9, MAT['cedar_lt'], C['buildings'])

# Bar stools
for dx in [-1.2, 0, 1.2]:
    cyl(f"Stool_{dx}", -30+dx, -3.8, 0.35, 0.18, 0.04, MAT['cushion_dk'], C['furniture'])
    cyl(f"Stool_Leg_{dx}", -30+dx, -3.8, 0.17, 0.03, 0.34, MAT['steel'], C['furniture'])

print("  Done: 7 buildings + coffee bar")

# ═══════════════════════════════════════════
# SWIMMING POOL — the centerpiece outdoor feature
# ═══════════════════════════════════════════
print("[3/10] Swimming pool...")

PX, PY = -8, -32  # pool center

# Pool deck (large concrete pad)
box("Pool_Deck", PX, PY, 0.08, 22, 14, 0.16, MAT['tile_pool'], C['pool'], 0.02)

# Pool basin (recessed)
box("Pool_Shell", PX - 2, PY, -0.3, 14, 8, 1.5, MAT['tile_blue'], C['pool'], 0.03)

# Pool water surface
bpy.ops.mesh.primitive_plane_add(size=1, location=(PX - 2, PY, 0.05))
pw = bpy.context.active_object
pw.name = "Pool_Water"
pw.dimensions = (13.6, 7.6, 0)
bpy.ops.object.transform_apply(scale=True)
pw.data.materials.append(MAT['water_pool'])
link_to(pw, C['pool'])

# Pool edge coping
for loc, dims in [
    ((PX-2, PY-4.2, 0.12), (14.4, 0.4, 0.12)),
    ((PX-2, PY+4.2, 0.12), (14.4, 0.4, 0.12)),
    ((PX-9.2, PY, 0.12), (0.4, 8.4, 0.12)),
    ((PX+5.2, PY, 0.12), (0.4, 8.4, 0.12)),
]:
    box("Pool_Coping", *loc, *dims, MAT['concrete_lt'], C['pool'], 0.01)

# Lounge chairs along pool (6)
for i in range(6):
    lx = PX - 7 + i * 2.5
    ly = PY + 5.5
    make_lounge_chair(f"Lounge_{i}", lx, ly, coll=C['pool'])

# Umbrellas (3 large)
for i, ux in enumerate([PX - 5, PX - 0.5, PX + 4]):
    cyl(f"Umbrella_Pole_{i}", ux, PY + 5.5, 1.3, 0.04, 2.6, MAT['steel'], C['pool'])
    cyl(f"Umbrella_Top_{i}", ux, PY + 5.5, 2.7, 1.5, 0.05, MAT['fabric'], C['pool'])

# Small round tables between lounges
for i, tx in enumerate([PX - 4.5, PX + 0.5]):
    make_table(f"Pool_Table_{i}", tx, PY + 5.5, coll=C['pool'])

print("  Done: 14x8m pool with deck, lounges, umbrellas")

# ═══════════════════════════════════════════
# SPA WELLNESS — sauna, cold plunge, hot tubs
# ═══════════════════════════════════════════
print("[4/10] Spa & wellness...")

SX, SY = 22, -28  # spa area center (east of pool)

# Spa deck
box("Spa_Deck", SX, SY, 0.08, 16, 12, 0.16, MAT['deck'], C['spa'], 0.02)

# Barrel sauna (outdoor, visible)
cyl("Sauna_Barrel", SX - 3, SY + 2, 1.2, 1.2, 2.8, MAT['sauna_wd'], C['spa'])
# Rotate barrel on its side
bpy.data.objects["Sauna_Barrel"].rotation_euler[1] = math.radians(90)

# Sauna door end cap
cyl("Sauna_End", SX - 3 - 1.4, SY + 2, 1.2, 1.18, 0.08, MAT['cedar_dark'], C['spa'])
bpy.data.objects["Sauna_End"].rotation_euler[1] = math.radians(90)

# Sauna chimney
cyl("Sauna_Chimney", SX - 3, SY + 2, 2.6, 0.08, 0.5, MAT['steel'], C['spa'])

# Cold plunge pool (rectangular, visible)
box("ColdPlunge_Shell", SX + 2, SY + 2, 0.2, 3.0, 2.0, 1.2, MAT['concrete'], C['spa'], 0.02)
# Solidify for basin
bpy.data.objects["ColdPlunge_Shell"].modifiers.new('Solidify', 'SOLIDIFY')
bpy.data.objects["ColdPlunge_Shell"].modifiers['Solidify'].thickness = 0.1
bpy.data.objects["ColdPlunge_Shell"].modifiers['Solidify'].offset = -1

# Cold plunge water
bpy.ops.mesh.primitive_plane_add(size=1, location=(SX + 2, SY + 2, 0.7))
cpw = bpy.context.active_object
cpw.name = "ColdPlunge_Water"
cpw.dimensions = (2.8, 1.8, 0)
bpy.ops.object.transform_apply(scale=True)
cpw.data.materials.append(MAT['water_cold'])
link_to(cpw, C['spa'])

# Hot tubs (2 round cedar tubs)
for i, (hx, hy) in enumerate([(SX - 3, SY - 3), (SX + 2, SY - 3)]):
    # Outer shell
    ht = cyl(f"HotTub_{i+1}", hx, hy, 0.55, 1.2, 0.9, MAT['cedar_lt'], C['spa'])
    bpy.ops.object.modifier_add(type='SOLIDIFY')
    ht.modifiers['Solidify'].thickness = 0.10
    ht.modifiers['Solidify'].offset = -1
    bpy.ops.object.modifier_add(type='BEVEL')
    ht.modifiers['Bevel'].width = 0.015
    ht.modifiers['Bevel'].segments = 3

    # Water
    cyl(f"HotTub_{i+1}_Water", hx, hy, 0.85, 1.05, 0.02, MAT['water_warm'], C['spa'])

# Spa seating area (benches around hot tubs)
make_bench("Spa_Bench_1", SX - 0.5, SY - 5, coll=C['spa'])
make_bench("Spa_Bench_2", SX + 5.5, SY, angle=90, coll=C['spa'])

# Towel hooks / small storage
box("Towel_Rack", SX + 6, SY + 3, 1.0, 0.8, 0.3, 1.6, MAT['cedar'], C['spa'], 0.008)

print("  Done: barrel sauna, cold plunge, 2 hot tubs, benches")

# ═══════════════════════════════════════════
# LANDSCAPE — trees, beds, hedges, flowers
# ═══════════════════════════════════════════
print("[5/10] Landscape...")

# Raised garden beds (NW, 4x6 grid)
for row in range(4):
    for ci in range(6):
        x = -38 + ci * 3.8
        y = 20 + row * 3.5
        box(f"Bed_{row}_{ci}", x, y, 0.25, 3.0, 1.2, 0.5, MAT['cedar_lt'], C['landscape'])
        box(f"Soil_{row}_{ci}", x, y, 0.48, 2.9, 1.1, 0.04, MAT['soil'], C['landscape'], 0)

# Orchard trees (NE)
for i in range(12):
    tx = 28 + (i % 4) * 5
    ty = 22 + (i // 4) * 5
    make_tree(f"Tree_{i+1}", tx, ty, height=3.5 + (i % 3) * 0.5)

# Decorative trees scattered around campus
tree_spots = [
    (-35, -15), (-35, 15), (35, 15), (-12, -38), (12, -38),
    (-38, 0), (38, 0), (-15, 35), (15, 35),
    (-28, -28), (28, 28),
]
for i, (tx, ty) in enumerate(tree_spots):
    make_tree(f"Deco_Tree_{i}", tx, ty, height=2.5 + (i % 3), canopy_r=1.3 + (i % 2) * 0.5)

# Hedges — lining key paths and areas
make_hedge("Hedge_Entry_W", -4, -15, 6, along_x=False)
make_hedge("Hedge_Entry_E", 4, -15, 6, along_x=False)
make_hedge("Hedge_Pool_N", PX, PY + 7.5, 22, height=1.0)
make_hedge("Hedge_Pool_S", PX, PY - 7.5, 22, height=1.0)
make_hedge("Hedge_Spa_N", SX, SY + 6.5, 16, height=1.0)
make_hedge("Hedge_Garden_S", -19, 18, 24, height=0.9)

# Shrubs at building entrances
for sx, sy in [
    (-3, -14), (3, -14),        # Welcome
    (-14, 3), (-14, 13),        # Dining
    (17, 5), (17, 15),          # Education
    (-17, -3), (-17, -13),      # Maker
    (16, -3), (16, -13),        # Movement
]:
    make_shrub(f"Shrub_{sx}_{sy}", sx, sy, radius=0.5)

# Flower beds along paths
flower_mats = [MAT['flowers_red'], MAT['flowers_purp'], MAT['flowers_yel']]
for i in range(20):
    angle_rad = math.radians(i * 18)
    fx = math.cos(angle_rad) * 8
    fy = math.sin(angle_rad) * 8
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, segments=8, ring_count=6,
                                          location=(fx, fy, 0.15))
    fl = bpy.context.active_object
    fl.name = f"Flower_{i}"
    fl.scale[2] = 0.4
    bpy.ops.object.transform_apply(scale=True)
    fl.data.materials.append(flower_mats[i % 3])
    link_to(fl, C['landscape'])

# Fire pit area (SW)
cyl("Fire_Pit", -24, -24, 0.25, 0.7, 0.5, MAT['concrete'], C['landscape'])
# Fire glow
pit_fire = cyl("Fire_Glow", -24, -24, 0.45, 0.4, 0.1, MAT['screen'], C['landscape'])  # emission

# Seating ring around fire
bpy.ops.mesh.primitive_torus_add(major_radius=2.5, minor_radius=0.25, location=(-24, -24, 0.45))
seat_ring = bpy.context.active_object
seat_ring.name = "Fire_Seating"
seat_ring.data.materials.append(MAT['cedar'])
link_to(seat_ring, C['landscape'])

# Adirondack chairs around fire pit (6)
for i in range(6):
    fa = math.radians(i * 60 + 15)
    fcx = -24 + math.cos(fa) * 3.5
    fcy = -24 + math.sin(fa) * 3.5
    make_chair(f"Fire_Chair_{i}", fcx, fcy, coll=C['landscape'])

# Central courtyard fountain
cyl("Fountain_Basin", 0, 0, 0.3, 2.5, 0.6, MAT['concrete'], C['landscape'])
bpy.data.objects["Fountain_Basin"].modifiers.new('Solidify', 'SOLIDIFY')
bpy.data.objects["Fountain_Basin"].modifiers['Solidify'].thickness = 0.15
bpy.data.objects["Fountain_Basin"].modifiers['Solidify'].offset = -1
cyl("Fountain_Water", 0, 0, 0.45, 2.3, 0.02, MAT['water_pool'], C['landscape'])
cyl("Fountain_Jet", 0, 0, 0.8, 0.08, 0.7, MAT['concrete'], C['landscape'])

# Reflecting pool (north, near greenhouse)
box("Reflect_Pool", 0, 38, 0.0, 14, 3, 0.5, MAT['concrete'], C['landscape'], 0.02)
bpy.data.objects["Reflect_Pool"].modifiers.new('Solidify', 'SOLIDIFY')
bpy.data.objects["Reflect_Pool"].modifiers['Solidify'].thickness = 0.1
bpy.data.objects["Reflect_Pool"].modifiers['Solidify'].offset = -1
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 38, 0.2))
rpw = bpy.context.active_object
rpw.name = "Reflect_Water"
rpw.dimensions = (13.6, 2.6, 0)
bpy.ops.object.transform_apply(scale=True)
rpw.data.materials.append(MAT['water_pool'])
link_to(rpw, C['landscape'])

print("  Done: beds, orchard, 23 trees, hedges, shrubs, flowers, fire pit, fountain")

# ═══════════════════════════════════════════
# OUTDOOR SEATING AREAS
# ═══════════════════════════════════════════
print("[6/10] Outdoor seating...")

# Dining patio (west of dining hall, 4 tables with chairs)
box("Dining_Patio", -30, 14, 0.05, 8, 8, 0.1, MAT['stone_path'], C['furniture'], 0.01)
for i in range(4):
    tx = -32 + (i % 2) * 4
    ty = 12 + (i // 2) * 4
    make_table(f"Dining_Table_{i}", tx, ty, coll=C['furniture'])
    for j in range(4):
        ca = math.radians(j * 90 + 45)
        make_chair(f"Dining_Chair_{i}_{j}", tx + math.cos(ca)*0.8, ty + math.sin(ca)*0.8, coll=C['furniture'])

# Garden viewing benches (along garden beds)
for i in range(3):
    make_bench(f"Garden_Bench_{i}", -38 + i * 10, 17, angle=0, coll=C['furniture'])

# Central courtyard benches (around fountain)
for i in range(4):
    ba = math.radians(i * 90 + 45)
    bx = math.cos(ba) * 5
    by = math.sin(ba) * 5
    make_bench(f"Court_Bench_{i}", bx, by, angle=i*90, coll=C['furniture'])

# Yoga/meditation area with mats (east)
box("Yoga_Deck", 35, -5, 0.05, 12, 12, 0.1, MAT['deck'], C['furniture'], 0.01)
for row in range(3):
    for ci in range(3):
        box(f"Yoga_Mat_{row}_{ci}", 32 + ci * 3, -8 + row * 3, 0.12, 1.8, 0.7, 0.03,
            MAT['cushion'], C['furniture'], 0.005)

print("  Done: dining patio, garden benches, courtyard seating, yoga mats")

# ═══════════════════════════════════════════
# COVERED WALKWAYS
# ═══════════════════════════════════════════
print("[7/10] Walkways...")

make_walkway("WK_W_to_D", -4, -14, -15, 3)
make_walkway("WK_W_to_M", -4, -15, -17, -4)
make_walkway("WK_W_to_Mv", 4, -14, 16, -5)
make_walkway("WK_W_to_E", 4, -14, 17, 5)
make_walkway("WK_D_to_GH", -15, 12, -8, 18)
make_walkway("WK_E_to_GH", 17, 14, 9, 18)
make_walkway("WK_to_Pool", 4, -22, PX + 8, PY + 7)

# Radial ground paths from center (no canopy)
for angle_deg in [0, 45, 90, 135, 180, 225, 270, 315]:
    a = math.radians(angle_deg)
    x2 = math.cos(a) * 14
    y2 = math.sin(a) * 14
    length = math.sqrt(x2*x2 + y2*y2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x2/2, y2/2, 0.025))
    rp = bpy.context.active_object
    rp.name = f"RadPath_{angle_deg}"
    rp.dimensions = (length, 1.8, 0.05)
    rp.rotation_euler = (0, 0, math.atan2(y2, x2))
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    rp.data.materials.append(MAT['stone_path'])
    link_to(rp, C['paths'])

# Perimeter running circuit
S = 90.0
INSET = 5.0
for side, loc, dims in [
    ("S", (0, -S/2+INSET, 0.03), (S-2*INSET, 2.0, 0.04)),
    ("N", (0, S/2-INSET, 0.03), (S-2*INSET, 2.0, 0.04)),
    ("W", (-S/2+INSET, 0, 0.03), (2.0, S-2*INSET, 0.04)),
    ("E", (S/2-INSET, 0, 0.03), (2.0, S-2*INSET, 0.04)),
]:
    box(f"Circuit_{side}", *loc, *dims, MAT['track'], C['paths'], 0.005)

print("  Done")

# ═══════════════════════════════════════════
# TECH OVERLAY
# ═══════════════════════════════════════════
print("[8/10] Tech overlay...")

speaker_locs = [
    (-3, -18, 3.5), (3, -18, 3.5),
    (-5, 22, 4), (0, 28, 4), (5, 22, 4),
    (-25, 8, 3.5), (-19, 8, 3.5),
    (20, 8, 3.5), (24, 12, 3.5),
    (-24, -8, 4), (-20, -8, 4),
    (20, -10, 3.5), (24, -6, 3.5),
    (10, -28, 3), (PX, PY + 7, 2),
    (0, 0, 2.5), (-24, -24, 2), (35, -5, 2),
]
for i, (x, y, z) in enumerate(speaker_locs):
    box(f"Speaker_{i+1}", x, y, z, 0.18, 0.18, 0.25, MAT['speaker'], C['tech'], 0.005)

edu_scr = [(20, 14.5, 2.8), (24, 14.5, 2.8), (22, 9.5, 2.8), (22, 14.5, 2.8)]
for i, (x, y, z) in enumerate(edu_scr):
    box(f"Screen_Edu_{i}", x, y, z, 1.6, 0.04, 0.9, MAT['screen'], C['tech'], 0)

print("  Done")

# ═══════════════════════════════════════════
# RENDER SETUP — Cycles + AgX + Sun/Sky
# ═══════════════════════════════════════════
print("[9/10] Render settings...")

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
scene.view_settings.exposure = 0.4

scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# World: Hosek-Wilkie sky with warm afternoon sun
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
for n in wn:
    wn.remove(n)

sky = wn.new('ShaderNodeTexSky')
sky.sky_type = 'HOSEK_WILKIE'
sky.sun_elevation = math.radians(35)   # lower sun = warmer, longer shadows
sky.sun_rotation = math.radians(-30)
try:
    sky.turbidity = 3.0  # slight haze for warmth
except:
    pass

bg = wn.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value = 1.2
out = wn.new('ShaderNodeOutputWorld')
wl.new(sky.outputs['Color'], bg.inputs['Color'])
wl.new(bg.outputs['Background'], out.inputs['Surface'])

# Sun light — warm afternoon
bpy.ops.object.light_add(type='SUN', location=(30, -30, 50))
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = 4.0
sun.data.angle = math.radians(0.5)  # soft shadows
sun.rotation_euler = (math.radians(35), math.radians(15), math.radians(-30))

# Warm fill light from opposite side
bpy.ops.object.light_add(type='SUN', location=(-20, 20, 40))
fill = bpy.context.active_object
fill.name = "Fill_Sun"
fill.data.energy = 0.8
fill.data.angle = math.radians(2.0)
fill.rotation_euler = (math.radians(55), math.radians(-10), math.radians(150))

# Post-processing: compositor
try:
    scene.use_nodes = True
    comp = scene.node_tree
    if comp is None:
        # Blender 5.1+ may use compositor_node_tree
        comp = getattr(scene, 'compositor_node_tree', None)
    if comp:
        comp_nodes = comp.nodes
        comp_links = comp.links
        for n in comp_nodes:
            comp_nodes.remove(n)

        rl = comp_nodes.new('CompositorNodeRLayers')
        composite = comp_nodes.new('CompositorNodeComposite')

        glare = comp_nodes.new('CompositorNodeGlare')
        glare.glare_type = 'FOG_GLOW'
        glare.quality = 'HIGH'
        glare.threshold = 3.0

        lens = comp_nodes.new('CompositorNodeLensdist')
        lens.inputs['Dispersion'].default_value = 0.008

        comp_links.new(rl.outputs['Image'], glare.inputs['Image'])
        comp_links.new(glare.outputs['Image'], lens.inputs['Image'])
        comp_links.new(lens.outputs['Image'], composite.inputs['Image'])
        print("  Compositor: glare + lens distortion enabled")
    else:
        print("  Compositor: not available in this Blender version, skipping")
except Exception as e:
    print(f"  Compositor setup skipped: {e}")

print("  Done: Cycles 2048spp + AgX + warm afternoon + compositor")

# ═══════════════════════════════════════════
# CAMERAS — better angles for attractive shots
# ═══════════════════════════════════════════
print("[10/10] Cameras...")

# Aerial overview
bpy.ops.object.camera_add(location=(0, 0, 85))
cam1 = bpy.context.active_object
cam1.name = "CAM_aerial_overview"
cam1.data.type = 'ORTHO'
cam1.data.ortho_scale = 100
cam1.rotation_euler = (0, 0, 0)

# Hero perspective — lower, more dramatic
bpy.ops.object.camera_add(location=(55, -50, 30))
cam2 = bpy.context.active_object
cam2.name = "CAM_perspective_hero"
cam2.data.lens = 28
cam2.data.sensor_width = 36
cam2.data.clip_end = 500
cam2.rotation_euler = (math.radians(65), 0, math.radians(42))

# Pool & spa view — showcasing the amenities
bpy.ops.object.camera_add(location=(-30, -55, 15))
cam3 = bpy.context.active_object
cam3.name = "CAM_pool_spa"
cam3.data.lens = 35
cam3.data.sensor_width = 36
cam3.data.clip_end = 500
cam3.rotation_euler = (math.radians(78), 0, math.radians(-20))
# DOF for pool shot
cam3.data.dof.use_dof = True
cam3.data.dof.aperture_fstop = 4.0
cam3.data.dof.focus_distance = 30

# Entrance approach — eye level
bpy.ops.object.camera_add(location=(0, -50, 5))
cam4 = bpy.context.active_object
cam4.name = "CAM_entrance"
cam4.data.lens = 28
cam4.data.sensor_width = 36
cam4.data.clip_end = 500
cam4.rotation_euler = (math.radians(86), 0, 0)

# Garden detail
bpy.ops.object.camera_add(location=(-30, 30, 8))
cam5 = bpy.context.active_object
cam5.name = "CAM_garden_detail"
cam5.data.lens = 50
cam5.data.sensor_width = 36
cam5.data.clip_end = 500
cam5.data.dof.use_dof = True
cam5.data.dof.aperture_fstop = 2.8
cam5.data.dof.focus_distance = 12
cam5.rotation_euler = (math.radians(72), 0, math.radians(-135))

scene.camera = cam2

# ═══════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════
RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v7")
os.makedirs(RENDER_DIR, exist_ok=True)

scene.render.image_settings.file_format = 'PNG'

for cam_name in ['CAM_aerial_overview', 'CAM_perspective_hero', 'CAM_pool_spa', 'CAM_entrance', 'CAM_garden_detail']:
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        continue
    scene.camera = cam_obj
    out_path = os.path.join(RENDER_DIR, f"v7_{cam_name}.png")
    scene.render.filepath = out_path
    print(f"  Rendering {cam_name}...")
    bpy.ops.render.render(write_still=True)
    print(f"  Saved: {out_path}")

save_path = os.path.expanduser("~/Projects/sponic-garden-3d/sponic-garden-v7.blend")
bpy.ops.wm.save_as_mainfile(filepath=save_path)
print(f"\nDone! Saved to {save_path}")
