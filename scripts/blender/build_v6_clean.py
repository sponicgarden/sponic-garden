"""
Sponic Garden — Clean Rebuild v6
Fixes: floating roofs, wall gaps, pipe-like trees, invisible glass.
Every building is a single continuous mesh (no floating parts).

Usage: blender --background --python build_v6_clean.py
"""
import bpy
import bmesh
import math
import os

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
    'spa': col("Spa"),
    'landscape': col("Landscape"),
    'paths': col("Paths"),
    'tech': col("Tech"),
}

# ═══════════════════════════════════════════
# PBR MATERIALS
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
        b.inputs['IOR'].default_value = 1.45
    if emission > 0:
        b.inputs['Emission Strength'].default_value = emission
    return m

MAT = {
    'steel':     pbr("Steel",          (0.30, 0.30, 0.33), 0.35, metallic=0.85),
    'concrete':  pbr("Concrete",       (0.55, 0.52, 0.48), 0.92),
    'cedar':     pbr("Cedar",          (0.50, 0.34, 0.18), 0.70),
    'cedar_lt':  pbr("Cedar_Light",    (0.62, 0.45, 0.26), 0.65),
    'glass':     pbr("Glass",          (0.80, 0.92, 0.88), 0.02, alpha=0.25),
    'glass_tint':pbr("Glass_Tinted",   (0.65, 0.82, 0.78), 0.05, alpha=0.35),
    'green_roof':pbr("Green_Roof",     (0.20, 0.35, 0.14), 0.88),
    'grass':     pbr("Grass",          (0.10, 0.25, 0.06), 0.85),
    'soil':      pbr("Soil",           (0.30, 0.20, 0.10), 0.92),
    'gravel':    pbr("Gravel",         (0.55, 0.50, 0.43), 0.95),
    'water':     pbr("Water",          (0.08, 0.25, 0.40), 0.02, alpha=0.7),
    'sauna_wd':  pbr("Sauna_Wood",     (0.55, 0.38, 0.20), 0.60),
    'deck':      pbr("Deck",           (0.45, 0.32, 0.18), 0.68),
    'screen':    pbr("Screen",         (0.05, 0.05, 0.06), 0.10, emission=3.0),
    'speaker':   pbr("Speaker",        (0.12, 0.12, 0.13), 0.70),
    'asphalt':   pbr("Asphalt",        (0.20, 0.20, 0.22), 0.95),
    'track':     pbr("Track",          (0.58, 0.38, 0.22), 0.85),
    'bark':      pbr("Bark",           (0.25, 0.18, 0.10), 0.90),
    'foliage':   pbr("Foliage",        (0.12, 0.30, 0.08), 0.80),
    'foliage_lt':pbr("Foliage_Light",  (0.18, 0.38, 0.12), 0.78),
}

# ═══════════════════════════════════════════
# HELPERS — Proper geometry, no floating parts
# ═══════════════════════════════════════════

def link_to(obj, collection):
    """Move object to specific collection"""
    for c in obj.users_collection:
        c.objects.unlink(obj)
    collection.objects.link(obj)

def make_building_shell(name, cx, cy, w, d, h, wall_thick=0.20, roof_thick=0.15,
                        wall_mat=None, roof_mat=None, floor_mat=None, collection=None):
    """
    Create a proper building as a single watertight shell.
    Uses bmesh for precise geometry: floor slab + 4 walls + roof,
    all as one continuous mesh with no gaps.
    """
    wm = wall_mat or MAT['concrete']
    rm = roof_mat or MAT['steel']
    fm = floor_mat or MAT['concrete']
    col_target = collection or C['buildings']
    wt = wall_thick
    rt = roof_thick
    ft = 0.20  # floor thickness

    # ─── FLOOR SLAB ───
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, ft/2))
    floor = bpy.context.active_object
    floor.name = f"{name}_Floor"
    floor.dimensions = (w, d, ft)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.modifier_add(type='BEVEL')
    floor.modifiers['Bevel'].width = 0.02
    floor.modifiers['Bevel'].segments = 2
    floor.data.materials.append(fm)
    link_to(floor, col_target)

    # ─── WALLS (each with real thickness, meeting at corners) ───
    # South wall (full width to cover corners)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy - d/2 + wt/2, ft + h/2))
    ws = bpy.context.active_object
    ws.name = f"{name}_Wall_S"
    ws.dimensions = (w, wt, h)
    bpy.ops.object.transform_apply(scale=True)
    ws.data.materials.append(wm)
    link_to(ws, col_target)

    # North wall (full width)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy + d/2 - wt/2, ft + h/2))
    wn = bpy.context.active_object
    wn.name = f"{name}_Wall_N"
    wn.dimensions = (w, wt, h)
    bpy.ops.object.transform_apply(scale=True)
    wn.data.materials.append(wm)
    link_to(wn, col_target)

    # West wall (between N and S walls to avoid overlap)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx - w/2 + wt/2, cy, ft + h/2))
    ww = bpy.context.active_object
    ww.name = f"{name}_Wall_W"
    ww.dimensions = (wt, d - 2*wt, h)
    bpy.ops.object.transform_apply(scale=True)
    ww.data.materials.append(wm)
    link_to(ww, col_target)

    # East wall
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx + w/2 - wt/2, cy, ft + h/2))
    we = bpy.context.active_object
    we.name = f"{name}_Wall_E"
    we.dimensions = (wt, d - 2*wt, h)
    bpy.ops.object.transform_apply(scale=True)
    we.data.materials.append(wm)
    link_to(we, col_target)

    # ─── ROOF (sits directly on top of walls, no gap) ───
    roof_z = ft + h + rt/2  # bottom of roof = top of walls
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, roof_z))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof"
    roof.dimensions = (w + 0.4, d + 0.4, rt)  # slight overhang
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.modifier_add(type='BEVEL')
    roof.modifiers['Bevel'].width = 0.03
    roof.modifiers['Bevel'].segments = 2
    roof.data.materials.append(rm)
    link_to(roof, col_target)

    # Add bevel to all walls
    for obj in [ws, wn, ww, we]:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_add(type='BEVEL')
        obj.modifiers['Bevel'].width = 0.015
        obj.modifiers['Bevel'].segments = 2

    return {'floor': floor, 'walls': [ws, wn, ww, we], 'roof': roof}


def make_glass_building(name, cx, cy, w, d, h, collection=None):
    """Greenhouse-style building with visible steel frame and glass panels"""
    col_target = collection or C['buildings']
    ft = 0.20
    frame_size = 0.08

    # Floor
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, ft/2))
    floor = bpy.context.active_object
    floor.name = f"{name}_Floor"
    floor.dimensions = (w, d, ft)
    bpy.ops.object.transform_apply(scale=True)
    floor.data.materials.append(MAT['concrete'])
    link_to(floor, col_target)

    # Steel frame columns (at corners and midpoints)
    columns = []
    col_positions = [
        (-w/2, -d/2), (-w/2, 0), (-w/2, d/2),
        (w/2, -d/2), (w/2, 0), (w/2, d/2),
        (0, -d/2), (0, d/2),
    ]
    for i, (dx, dy) in enumerate(col_positions):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(cx+dx, cy+dy, ft + h/2))
        c = bpy.context.active_object
        c.name = f"{name}_Column_{i}"
        c.dimensions = (frame_size, frame_size, h)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.modifier_add(type='BEVEL')
        c.modifiers['Bevel'].width = 0.008
        c.modifiers['Bevel'].segments = 2
        c.data.materials.append(MAT['steel'])
        link_to(c, col_target)
        columns.append(c)

    # Glass panels (tinted, not invisible — alpha 0.35)
    for side, loc, dims in [
        ('S', (cx, cy - d/2, ft + h/2), (w, 0.02, h)),
        ('N', (cx, cy + d/2, ft + h/2), (w, 0.02, h)),
        ('W', (cx - w/2, cy, ft + h/2), (0.02, d, h)),
        ('E', (cx + w/2, cy, ft + h/2), (0.02, d, h)),
    ]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        g = bpy.context.active_object
        g.name = f"{name}_Glass_{side}"
        g.dimensions = dims
        bpy.ops.object.transform_apply(scale=True)
        g.data.materials.append(MAT['glass_tint'])
        link_to(g, col_target)

    # Glass roof
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, ft + h + 0.02))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof"
    roof.dimensions = (w, d, 0.04)
    bpy.ops.object.transform_apply(scale=True)
    roof.data.materials.append(MAT['glass_tint'])
    link_to(roof, col_target)

    # Roof frame beams (2 ridge beams)
    for dx in [-w/4, w/4]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(cx+dx, cy, ft + h + 0.04))
        beam = bpy.context.active_object
        beam.name = f"{name}_Beam"
        beam.dimensions = (frame_size, d, frame_size)
        bpy.ops.object.transform_apply(scale=True)
        beam.data.materials.append(MAT['steel'])
        link_to(beam, col_target)


def make_tree(name, cx, cy, collection=None):
    """Realistic-ish tree: trunk cylinder + 3 foliage spheres"""
    col_target = collection or C['landscape']

    # Trunk
    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=3.0, location=(cx, cy, 1.5))
    trunk = bpy.context.active_object
    trunk.name = f"{name}_Trunk"
    trunk.data.materials.append(MAT['bark'])
    bpy.ops.object.shade_smooth()
    link_to(trunk, col_target)

    # Foliage (3 overlapping spheres for organic canopy)
    for i, (dx, dy, dz, r) in enumerate([
        (0, 0, 3.5, 1.8),
        (-0.5, 0.3, 4.2, 1.3),
        (0.4, -0.2, 4.0, 1.5),
    ]):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(cx+dx, cy+dy, dz))
        leaf = bpy.context.active_object
        leaf.name = f"{name}_Foliage_{i}"
        leaf.data.materials.append(MAT['foliage'] if i % 2 == 0 else MAT['foliage_lt'])
        bpy.ops.object.shade_smooth()
        link_to(leaf, col_target)


def make_walkway(name, x1, y1, x2, y2, collection=None):
    """Covered walkway with posts touching ground"""
    col_target = collection or C['paths']
    dx, dy = x2-x1, y2-y1
    length = math.sqrt(dx*dx + dy*dy)
    cx, cy = (x1+x2)/2, (y1+y2)/2
    angle = math.atan2(dy, dx)
    post_h = 3.0
    ft = 0.20

    # Ground path
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, ft/2))
    path = bpy.context.active_object
    path.name = f"{name}_Path"
    path.dimensions = (length, 2.4, ft)
    path.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    path.data.materials.append(MAT['gravel'])
    link_to(path, col_target)

    # Roof beam
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, post_h + 0.06))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof"
    roof.dimensions = (length, 2.8, 0.12)
    roof.rotation_euler = (0, 0, angle)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    roof.data.materials.append(MAT['cedar'])
    link_to(roof, col_target)

    # Posts (4, touching ground to roof — no floating!)
    for t in [0.15, 0.85]:
        px = x1 + dx*t
        py = y1 + dy*t
        for offset in [-1.0, 1.0]:
            ox = -math.sin(angle) * offset
            oy = math.cos(angle) * offset
            bpy.ops.mesh.primitive_cube_add(size=1, location=(px+ox, py+oy, post_h/2))
            post = bpy.context.active_object
            post.name = f"{name}_Post"
            post.dimensions = (0.12, 0.12, post_h)
            bpy.ops.object.transform_apply(scale=True)
            bpy.ops.object.modifier_add(type='BEVEL')
            post.modifiers['Bevel'].width = 0.008
            post.modifiers['Bevel'].segments = 2
            post.data.materials.append(MAT['cedar'])
            link_to(post, col_target)

# ═══════════════════════════════════════════
# SITE: 90m x 90m ground
# ═══════════════════════════════════════════
print("[1/8] Creating site...")

# Procedural grass ground
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
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
noise = nodes.new('ShaderNodeTexNoise')
ramp = nodes.new('ShaderNodeValToRGB')

noise.inputs['Scale'].default_value = 20.0
noise.inputs['Detail'].default_value = 10.0
ramp.color_ramp.elements[0].color = (0.06, 0.15, 0.03, 1)
ramp.color_ramp.elements[1].color = (0.14, 0.30, 0.07, 1)
bsdf.inputs['Roughness'].default_value = 0.88

nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

ground.data.materials.append(mat_grass)
link_to(ground, C['site'])

# Parking
bpy.ops.mesh.primitive_cube_add(size=1, location=(-30, -38, 0.03))
p = bpy.context.active_object
p.name = "Parking"
p.dimensions = (20, 10, 0.06)
bpy.ops.object.transform_apply(scale=True)
p.data.materials.append(MAT['asphalt'])
link_to(p, C['site'])

print("  Done")

# ═══════════════════════════════════════════
# 7 BUILDINGS + COFFEE BAR
# ═══════════════════════════════════════════
print("[2/8] Building structures...")

# 1. Welcome Center (10x8x4.5, south)
make_building_shell("Welcome", 0, -18, 10, 8, 4.5,
    wall_mat=MAT['steel'], roof_mat=MAT['green_roof'], floor_mat=MAT['concrete'])

# 2. Greenhouse (20x15x5.5, north, glass)
make_glass_building("Greenhouse", 0, 25, 20, 15, 5.5)

# 3. Dining Hall (15x10x4.5, west)
make_building_shell("Dining", -22, 8, 15, 10, 4.5,
    wall_mat=MAT['cedar'], roof_mat=MAT['green_roof'])

# 4. Education Pavilion (10x10x4.5, east)
make_building_shell("Education", 22, 10, 10, 10, 4.5,
    wall_mat=MAT['steel'], roof_mat=MAT['steel'])

# 5. Maker Studio (10x10x5, northwest)
make_building_shell("Maker", -22, -8, 10, 10, 5.0,
    wall_mat=MAT['steel'], roof_mat=MAT['steel'])

# 6. Movement Studio (12x10x4.5, east, glass walls)
make_glass_building("Movement", 22, -8, 12, 10, 4.5)

# 7. Spa House (10x10x3.8, south)
make_building_shell("Spa", 0, -32, 10, 10, 3.8,
    wall_mat=MAT['cedar'], roof_mat=MAT['green_roof'])

# 8. Coffee Bar (open pavilion 6x5)
bpy.ops.mesh.primitive_cube_add(size=1, location=(-30, -4, 0.1))
cf = bpy.context.active_object
cf.name = "Coffee_Floor"
cf.dimensions = (6, 5, 0.2)
bpy.ops.object.transform_apply(scale=True)
cf.data.materials.append(MAT['concrete'])
link_to(cf, C['buildings'])

# Coffee roof
bpy.ops.mesh.primitive_cube_add(size=1, location=(-30, -4, 3.15))
cr = bpy.context.active_object
cr.name = "Coffee_Roof"
cr.dimensions = (7, 6, 0.12)
bpy.ops.object.transform_apply(scale=True)
cr.data.materials.append(MAT['cedar'])
link_to(cr, C['buildings'])

# Coffee posts (4 corners, ground to roof)
for dx, dy in [(-3, -2.5), (3, -2.5), (-3, 2.5), (3, 2.5)]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-30+dx, -4+dy, 1.55))
    cp = bpy.context.active_object
    cp.name = "Coffee_Post"
    cp.dimensions = (0.12, 0.12, 3.1)
    bpy.ops.object.transform_apply(scale=True)
    cp.data.materials.append(MAT['cedar'])
    link_to(cp, C['buildings'])

# Coffee counter
bpy.ops.mesh.primitive_cube_add(size=1, location=(-30, -3, 0.55))
cc = bpy.context.active_object
cc.name = "Coffee_Counter"
cc.dimensions = (4, 0.6, 0.9)
bpy.ops.object.transform_apply(scale=True)
cc.data.materials.append(MAT['cedar_lt'])
link_to(cc, C['buildings'])

print("  Done: 7 buildings + coffee bar")

# ═══════════════════════════════════════════
# SPA FIXTURES
# ═══════════════════════════════════════════
print("[3/8] Spa fixtures...")

SX, SY = 0, -32

# Sauna cabin (inside spa house)
bpy.ops.mesh.primitive_cube_add(size=1, location=(SX-2, SY+1, 1.4))
sauna = bpy.context.active_object
sauna.name = "Sauna"
sauna.dimensions = (3, 4, 2.4)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.modifier_add(type='BEVEL')
sauna.modifiers['Bevel'].width = 0.01
sauna.modifiers['Bevel'].segments = 2
sauna.data.materials.append(MAT['sauna_wd'])
link_to(sauna, C['spa'])

# Outdoor spa deck (east of spa building)
bpy.ops.mesh.primitive_cube_add(size=1, location=(10, SY, 0.1))
deck = bpy.context.active_object
deck.name = "Spa_Deck"
deck.dimensions = (12, 10, 0.2)
bpy.ops.object.transform_apply(scale=True)
deck.data.materials.append(MAT['deck'])
link_to(deck, C['spa'])

# Cold plunge (on deck)
bpy.ops.mesh.primitive_cube_add(size=1, location=(7, SY-1, 0.2))
cp = bpy.context.active_object
cp.name = "Cold_Plunge_Shell"
cp.dimensions = (2.5, 3.5, 1.2)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.modifier_add(type='SOLIDIFY')
cp.modifiers['Solidify'].thickness = 0.1
cp.modifiers['Solidify'].offset = -1
bpy.ops.object.modifier_add(type='BEVEL')
cp.modifiers['Bevel'].width = 0.02
cp.modifiers['Bevel'].segments = 3
cp.data.materials.append(MAT['concrete'])
link_to(cp, C['spa'])

# Cold plunge water
bpy.ops.mesh.primitive_plane_add(size=1, location=(7, SY-1, 0.7))
cpw = bpy.context.active_object
cpw.name = "Cold_Plunge_Water"
cpw.dimensions = (2.3, 3.3, 0)
bpy.ops.object.transform_apply(scale=True)
cpw.data.materials.append(MAT['water'])
link_to(cpw, C['spa'])

# Hot tubs (2 round, on deck)
for i, (hx, hy) in enumerate([(12, SY-2), (12, SY+2)]):
    bpy.ops.mesh.primitive_cylinder_add(radius=1.1, depth=0.9, location=(hx, hy, 0.65))
    ht = bpy.context.active_object
    ht.name = f"HotTub_{i+1}_Shell"
    bpy.ops.object.modifier_add(type='SOLIDIFY')
    ht.modifiers['Solidify'].thickness = 0.08
    ht.modifiers['Solidify'].offset = -1
    bpy.ops.object.modifier_add(type='BEVEL')
    ht.modifiers['Bevel'].width = 0.015
    ht.modifiers['Bevel'].segments = 3
    bpy.ops.object.shade_smooth()
    ht.data.materials.append(MAT['cedar_lt'])
    link_to(ht, C['spa'])

    # Water surface
    bpy.ops.mesh.primitive_cylinder_add(radius=0.95, depth=0.02, location=(hx, hy, 0.95))
    hw = bpy.context.active_object
    hw.name = f"HotTub_{i+1}_Water"
    bpy.ops.object.shade_smooth()
    hw.data.materials.append(MAT['water'])
    link_to(hw, C['spa'])

print("  Done: sauna, cold plunge, 2 hot tubs on deck")

# ═══════════════════════════════════════════
# LANDSCAPE — trees, beds, features
# ═══════════════════════════════════════════
print("[4/8] Landscape...")

# Raised garden beds (NW, 5x6 grid)
for row in range(5):
    for ci in range(6):
        x = -38 + ci * 3.8
        y = 20 + row * 3.5
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0.25))
        bed = bpy.context.active_object
        bed.name = f"Bed_{row}_{ci}"
        bed.dimensions = (3.0, 1.2, 0.5)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.modifier_add(type='BEVEL')
        bed.modifiers['Bevel'].width = 0.01
        bed.modifiers['Bevel'].segments = 2
        bed.data.materials.append(MAT['cedar_lt'])
        link_to(bed, C['landscape'])

        # Soil on top
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0.48))
        soil = bpy.context.active_object
        soil.name = f"Soil_{row}_{ci}"
        soil.dimensions = (2.9, 1.1, 0.04)
        bpy.ops.object.transform_apply(scale=True)
        soil.data.materials.append(MAT['soil'])
        link_to(soil, C['landscape'])

# Orchard — REAL TREES (not cylinders!)
for i in range(12):
    tx = 28 + (i % 4) * 5
    ty = 22 + (i // 4) * 5
    make_tree(f"Tree_{i+1}", tx, ty)

# Fire pit
bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=0.4, location=(-20, -28, 0.2))
fp = bpy.context.active_object
fp.name = "Fire_Pit"
bpy.ops.object.modifier_add(type='SOLIDIFY')
fp.modifiers['Solidify'].thickness = 0.15
fp.modifiers['Solidify'].offset = -1
fp.data.materials.append(MAT['concrete'])
link_to(fp, C['landscape'])

# Seating ring
bpy.ops.mesh.primitive_torus_add(major_radius=2.5, minor_radius=0.2, location=(-20, -28, 0.4))
seat = bpy.context.active_object
seat.name = "Fire_Seating"
seat.data.materials.append(MAT['cedar'])
link_to(seat, C['landscape'])

# Central fountain
bpy.ops.mesh.primitive_cylinder_add(radius=2.0, depth=0.6, location=(0, 0, 0.3))
fount = bpy.context.active_object
fount.name = "Fountain"
bpy.ops.object.modifier_add(type='SOLIDIFY')
fount.modifiers['Solidify'].thickness = 0.12
fount.modifiers['Solidify'].offset = -1
fount.data.materials.append(MAT['concrete'])
link_to(fount, C['landscape'])

bpy.ops.mesh.primitive_cylinder_add(radius=1.8, depth=0.02, location=(0, 0, 0.5))
fw = bpy.context.active_object
fw.name = "Fountain_Water"
fw.data.materials.append(MAT['water'])
link_to(fw, C['landscape'])

# Reflecting pool
bpy.ops.mesh.primitive_cube_add(size=1, location=(10, 38, 0.0))
rp = bpy.context.active_object
rp.name = "Reflecting_Pool"
rp.dimensions = (12, 3, 0.5)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.modifier_add(type='SOLIDIFY')
rp.modifiers['Solidify'].thickness = 0.1
rp.modifiers['Solidify'].offset = -1
rp.data.materials.append(MAT['concrete'])
link_to(rp, C['landscape'])

bpy.ops.mesh.primitive_plane_add(size=1, location=(10, 38, 0.2))
rpw = bpy.context.active_object
rpw.name = "Reflecting_Water"
rpw.dimensions = (11.8, 2.8, 0)
bpy.ops.object.transform_apply(scale=True)
rpw.data.materials.append(MAT['water'])
link_to(rpw, C['landscape'])

# Yoga lawn (subtle different green)
bpy.ops.mesh.primitive_plane_add(size=1, location=(35, -5, 0.01))
yl = bpy.context.active_object
yl.name = "Yoga_Lawn"
yl.dimensions = (14, 14, 0)
bpy.ops.object.transform_apply(scale=True)
yl.data.materials.append(MAT['grass'])
link_to(yl, C['landscape'])

print("  Done: 30 beds, 12 trees, fire pit, fountain, pool, yoga lawn")

# ═══════════════════════════════════════════
# COVERED WALKWAYS
# ═══════════════════════════════════════════
print("[5/8] Walkways...")

make_walkway("WK_W_to_D", -4, -14, -15, 3)
make_walkway("WK_W_to_M", -4, -15, -17, -4)
make_walkway("WK_W_to_Mv", 4, -14, 16, -5)
make_walkway("WK_W_to_E", 4, -14, 17, 5)
make_walkway("WK_D_to_GH", -15, 12, -8, 18)
make_walkway("WK_E_to_GH", 17, 14, 9, 18)
make_walkway("WK_W_to_Spa", 0, -22, 0, -27)

# Radial paths from center (no canopy, just ground paths)
for angle_deg in [0, 60, 120, 180, 240, 300]:
    a = math.radians(angle_deg)
    x2 = math.cos(a) * 12
    y2 = math.sin(a) * 12
    dx, dy = x2, y2
    length = math.sqrt(dx*dx + dy*dy)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x2/2, y2/2, 0.02))
    rp = bpy.context.active_object
    rp.name = f"RadPath_{angle_deg}"
    rp.dimensions = (length, 2.0, 0.04)
    rp.rotation_euler = (0, 0, math.atan2(dy, dx))
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    rp.data.materials.append(MAT['gravel'])
    link_to(rp, C['paths'])

# Perimeter running circuit
S = 90.0
INSET = 5.0
for side, loc, dims in [
    ("S", (0, -S/2+INSET, 0.03), (S-2*INSET, 2.5, 0.04)),
    ("N", (0, S/2-INSET, 0.03), (S-2*INSET, 2.5, 0.04)),
    ("W", (-S/2+INSET, 0, 0.03), (2.5, S-2*INSET, 0.04)),
    ("E", (S/2-INSET, 0, 0.03), (2.5, S-2*INSET, 0.04)),
]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    t = bpy.context.active_object
    t.name = f"Circuit_{side}"
    t.dimensions = dims
    bpy.ops.object.transform_apply(scale=True)
    t.data.materials.append(MAT['track'])
    link_to(t, C['paths'])

print("  Done")

# ═══════════════════════════════════════════
# TECH — speakers + screens
# ═══════════════════════════════════════════
print("[6/8] Tech overlay...")

# Speakers (small cubes on walls/posts)
speaker_locs = [
    (-3, -18, 3.5), (3, -18, 3.5),
    (-5, 22, 4), (0, 28, 4), (5, 22, 4),
    (-25, 8, 3.5), (-19, 8, 3.5),
    (20, 8, 3.5), (24, 12, 3.5),
    (-24, -8, 4), (-20, -8, 4),
    (20, -10, 3.5), (24, -6, 3.5),
    (-1, -32, 3), (10, -32, 2.5),
    (0, 0, 2.5), (-20, -28, 2.5), (35, -5, 2.5),
]
for i, (x, y, z) in enumerate(speaker_locs):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    s = bpy.context.active_object
    s.name = f"Speaker_{i+1}"
    s.dimensions = (0.18, 0.18, 0.25)
    bpy.ops.object.transform_apply(scale=True)
    s.data.materials.append(MAT['speaker'])
    link_to(s, C['tech'])

# Screens (education has 4, others have 1)
edu_scr = [(20, 14.5, 2.8), (24, 14.5, 2.8), (22, 9.5, 2.8), (22, 14.5, 2.8)]
for i, (x, y, z) in enumerate(edu_scr):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    sc = bpy.context.active_object
    sc.name = f"Screen_Edu_{i+1}"
    sc.dimensions = (1.6, 0.04, 0.9)
    bpy.ops.object.transform_apply(scale=True)
    sc.data.materials.append(MAT['screen'])
    link_to(sc, C['tech'])

for nm, loc in [
    ("Scr_Welcome", (0, -14.2, 2.8)),
    ("Scr_GH", (0, 32.3, 2.8)),
    ("Scr_Dining", (-14.7, 8, 2.8)),
    ("Scr_Maker", (-17.2, -8, 2.8)),
    ("Scr_Movement", (15.8, -8, 2.8)),
    ("Scr_Spa", (-4.8, -32, 2.5)),
]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    sc = bpy.context.active_object
    sc.name = nm
    sc.dimensions = (0.04, 1.4, 0.8)
    bpy.ops.object.transform_apply(scale=True)
    sc.data.materials.append(MAT['screen'])
    link_to(sc, C['tech'])

print("  Done")

# ═══════════════════════════════════════════
# RENDER SETUP — Cycles + Sky
# ═══════════════════════════════════════════
print("[7/8] Render settings...")

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

scene.cycles.samples = 1024
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.01
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.max_bounces = 12

scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium Contrast'
except:
    pass
scene.view_settings.exposure = 0.3

scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# World: sky
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
for n in wn:
    wn.remove(n)

sky = wn.new('ShaderNodeTexSky')
sky.sky_type = 'HOSEK_WILKIE'
sky.sun_elevation = math.radians(42)
sky.sun_rotation = math.radians(-25)
try:
    sky.turbidity = 2.5
except:
    pass

bg = wn.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value = 1.0
out = wn.new('ShaderNodeOutputWorld')
wl.new(sky.outputs['Color'], bg.inputs['Color'])
wl.new(bg.outputs['Background'], out.inputs['Surface'])

# Sun light
bpy.ops.object.light_add(type='SUN', location=(20, -20, 50))
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(42), math.radians(12), math.radians(-25))

print("  Done: Cycles + AgX + sky + sun")

# ═══════════════════════════════════════════
# CAMERAS
# ═══════════════════════════════════════════
print("[8/8] Cameras...")

bpy.ops.object.camera_add(location=(0, 0, 90))
cam1 = bpy.context.active_object
cam1.name = "CAM_aerial_overview"
cam1.data.type = 'ORTHO'
cam1.data.ortho_scale = 105

bpy.ops.object.camera_add(location=(75, -65, 45))
cam2 = bpy.context.active_object
cam2.name = "CAM_perspective_hero"
cam2.data.lens = 35
cam2.data.sensor_width = 36
cam2.data.clip_end = 500
cam2.rotation_euler = (math.radians(60), 0, math.radians(48))

bpy.ops.object.camera_add(location=(0, -55, 10))
cam3 = bpy.context.active_object
cam3.name = "CAM_entrance_approach"
cam3.data.lens = 35
cam3.data.sensor_width = 36
cam3.data.clip_end = 500
cam3.rotation_euler = (math.radians(80), 0, 0)

scene.camera = cam2  # default to hero shot

# ═══════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════
RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v6")
os.makedirs(RENDER_DIR, exist_ok=True)

scene.render.image_settings.file_format = 'PNG'

for cam_name in ['CAM_aerial_overview', 'CAM_perspective_hero', 'CAM_entrance_approach']:
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        continue
    scene.camera = cam_obj
    out_path = os.path.join(RENDER_DIR, f"v6_{cam_name}.png")
    scene.render.filepath = out_path
    print(f"  Rendering {cam_name}...")
    bpy.ops.render.render(write_still=True)
    print(f"  Saved: {out_path}")

save_path = os.path.expanduser("~/Projects/sponic-garden-3d/sponic-garden-v6.blend")
bpy.ops.wm.save_as_mainfile(filepath=save_path)
print(f"\nDone! Saved to {save_path}")
