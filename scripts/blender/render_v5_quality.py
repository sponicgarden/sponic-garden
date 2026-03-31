"""
Sponic Garden — Quality Render Pipeline v5
Applies BLENDER-STANDARDS.md to the v4 model and renders with Cycles.

Usage:
  blender --background sponic-garden-v4.blend --python render_v5_quality.py

Fixes: floating objects, flat colors, no sky, no ground, EEVEE->Cycles
"""
import bpy
import math
import os

RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v5")
os.makedirs(RENDER_DIR, exist_ok=True)

scene = bpy.context.scene

# ═══════════════════════════════════════════
# STEP 1: Cycles + AgX + Denoiser
# ═══════════════════════════════════════════
print("[1/9] Setting render engine: Cycles + AgX...")

scene.render.engine = 'CYCLES'

# Enable Metal GPU on Apple Silicon
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = True
    scene.cycles.device = 'GPU'
except Exception as e:
    print(f"  GPU setup failed, using CPU: {e}")
    scene.cycles.device = 'CPU'

scene.cycles.samples = 1024  # balance quality vs time for test
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.01
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.max_bounces = 12
scene.cycles.diffuse_bounces = 4
scene.cycles.glossy_bounces = 4
scene.cycles.transparent_max_bounces = 8

# AgX color management
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium Contrast'
except:
    pass  # fallback if look not available
scene.view_settings.exposure = 0.5

# Resolution
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

print("  Done: Cycles GPU, 1024 samples, AgX, OIDN")

# ═══════════════════════════════════════════
# STEP 2: Nishita Sky (replaces gray void)
# ═══════════════════════════════════════════
print("[2/9] Adding Nishita sky...")

world = bpy.data.worlds.new("SponicWorld")
scene.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links

# Clear default nodes
for node in nodes:
    nodes.remove(node)

# Sky texture
sky = nodes.new('ShaderNodeTexSky')
# Blender 5.1 uses HOSEK_WILKIE or PREETHAM (NISHITA was renamed/removed)
sky.sky_type = 'HOSEK_WILKIE'
sky.sun_elevation = math.radians(42)
sky.sun_rotation = math.radians(-25)
try:
    sky.air_density = 1.0
    sky.dust_density = 0.3
except:
    pass  # Hosek/Wilkie uses turbidity instead
try:
    sky.turbidity = 2.5  # clear sky
except:
    pass

# Background
bg = nodes.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value = 1.0

# Output
output = nodes.new('ShaderNodeOutputWorld')

links.new(sky.outputs['Color'], bg.inputs['Color'])
links.new(bg.outputs['Background'], output.inputs['Surface'])

print("  Done: Nishita sky, sun at 42 deg elevation")

# ═══════════════════════════════════════════
# STEP 3: Ground plane with procedural grass
# ═══════════════════════════════════════════
print("[3/9] Creating ground plane with grass material...")

# Remove old flat ground if exists
for obj in bpy.data.objects:
    if obj.name == "Ground" and obj.type == 'MESH':
        bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.02))
ground = bpy.context.active_object
ground.name = "Ground_Terrain"

# Procedural grass material
mat_grass = bpy.data.materials.new("SPGD_landscape_grass_lawn")
mat_grass.use_nodes = True
nt = mat_grass.node_tree
for n in nt.nodes:
    nt.nodes.remove(n)

# Nodes
output_n = nt.nodes.new('ShaderNodeOutputMaterial')
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
noise1 = nt.nodes.new('ShaderNodeTexNoise')
noise2 = nt.nodes.new('ShaderNodeTexNoise')
color_ramp = nt.nodes.new('ShaderNodeValToRGB')
mix_rgb = nt.nodes.new('ShaderNodeMix')
mix_rgb.data_type = 'RGBA'
tex_coord = nt.nodes.new('ShaderNodeTexCoord')
mapping = nt.nodes.new('ShaderNodeMapping')

# Configure noise for grass variation
noise1.inputs['Scale'].default_value = 15.0
noise1.inputs['Detail'].default_value = 8.0
noise2.inputs['Scale'].default_value = 45.0
noise2.inputs['Detail'].default_value = 4.0

# Color ramp: dark green to light green
color_ramp.color_ramp.elements[0].color = (0.04, 0.12, 0.02, 1)  # dark grass
color_ramp.color_ramp.elements[1].color = (0.12, 0.28, 0.05, 1)  # light grass

# Mix two greens
mix_rgb.inputs['Factor'].default_value = 0.3

# Connect
nt.links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
nt.links.new(mapping.outputs['Vector'], noise1.inputs['Vector'])
nt.links.new(noise1.outputs['Fac'], color_ramp.inputs['Fac'])
nt.links.new(color_ramp.outputs['Color'], mix_rgb.inputs[6])  # A input
nt.links.new(noise2.outputs['Fac'], mix_rgb.inputs[7])  # B input
nt.links.new(mix_rgb.outputs[2], bsdf.inputs['Base Color'])  # Result

# Roughness
bsdf.inputs['Roughness'].default_value = 0.85

# Connect BSDF to output
nt.links.new(bsdf.outputs['BSDF'], output_n.inputs['Surface'])

ground.data.materials.append(mat_grass)

print("  Done: 200m grass ground plane")

# ═══════════════════════════════════════════
# STEP 4: PBR Materials for all objects
# ═══════════════════════════════════════════
print("[4/9] Applying PBR materials...")

def make_pbr(name, base_color, roughness, metallic=0.0, alpha=1.0, emission=0.0):
    """Create a proper PBR material"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (*base_color, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if alpha < 1.0:
        mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else None
        bsdf.inputs['Alpha'].default_value = alpha
        bsdf.inputs['IOR'].default_value = 1.52
    if emission > 0:
        bsdf.inputs['Emission Strength'].default_value = emission
        bsdf.inputs['Emission Color'].default_value = (0.9, 0.95, 1.0, 1.0)
    return mat

# Material library
materials = {
    'SPGD_structure_steel':     make_pbr("Steel_Frame",     (0.28, 0.28, 0.30), 0.35, metallic=0.85),
    'SPGD_structure_concrete':  make_pbr("Concrete",        (0.52, 0.50, 0.47), 0.92),
    'SPGD_structure_cedar':     make_pbr("Cedar_Wall",      (0.48, 0.32, 0.18), 0.72),
    'SPGD_structure_glass':     make_pbr("Glass",           (0.75, 0.88, 0.82), 0.05, alpha=0.18),
    'SPGD_landscape_path':      make_pbr("Gravel_Path",     (0.52, 0.47, 0.40), 0.95),
    'SPGD_landscape_growing':   make_pbr("Soil_Growing",    (0.15, 0.30, 0.08), 0.88),
    'SPGD_fixture_wood_deck':   make_pbr("Wood_Deck",       (0.42, 0.30, 0.16), 0.68),
    'SPGD_fixture_wood_light':  make_pbr("Wood_Light",      (0.55, 0.42, 0.25), 0.65),
    'SPGD_fixture_water':       make_pbr("Water",           (0.08, 0.28, 0.42), 0.05, alpha=0.6),
    'SPGD_fixture_sauna':       make_pbr("Sauna_Cedar",     (0.52, 0.35, 0.18), 0.62),
    'SPGD_dining':              make_pbr("Dining_Warm",     (0.55, 0.42, 0.18), 0.75),
    'SPGD_education':           make_pbr("Education_Blue",  (0.22, 0.32, 0.52), 0.78),
    'SPGD_maker':               make_pbr("Maker_Brown",     (0.42, 0.35, 0.22), 0.80),
    'SPGD_movement':            make_pbr("Movement_Orange", (0.52, 0.30, 0.15), 0.75),
    'SPGD_tech_screen':         make_pbr("Screen",          (0.05, 0.05, 0.06), 0.12, emission=2.0),
    'SPGD_tech_data':           make_pbr("Data_Flow",       (0.0, 0.55, 0.48),  0.40, metallic=0.3),
    'SPGD_parking':             make_pbr("Asphalt",         (0.18, 0.18, 0.19), 0.95),
    'SPGD_roof_green':          make_pbr("Green_Roof",      (0.18, 0.32, 0.12), 0.88),
    'SPGD_coffee':              make_pbr("Coffee_Bar",      (0.32, 0.20, 0.10), 0.70),
    'SPGD_track':               make_pbr("Running_Track",   (0.55, 0.35, 0.20), 0.85),
    'SPGD_pergola':             make_pbr("Pergola_Wood",    (0.38, 0.26, 0.14), 0.70),
}

# Map old material names to new PBR materials
material_map = {
    'Ground':         'SPGD_landscape_growing',
    'Path':           'SPGD_landscape_path',
    'Concrete':       'SPGD_structure_concrete',
    'Steel':          'SPGD_structure_steel',
    'Glass':          'SPGD_structure_glass',
    'Wood':           'SPGD_structure_cedar',
    'Wood_Light':     'SPGD_fixture_wood_light',
    'Growing':        'SPGD_landscape_growing',
    'Dining':         'SPGD_dining',
    'Education':      'SPGD_education',
    'Maker':          'SPGD_maker',
    'Movement':       'SPGD_movement',
    'Spa':            'SPGD_fixture_water',
    'Sauna':          'SPGD_fixture_sauna',
    'Water':          'SPGD_fixture_water',
    'Welcome':        'SPGD_structure_concrete',
    'Data_Flow':      'SPGD_tech_data',
    'Screen':         'SPGD_tech_screen',
    'Parking':        'SPGD_parking',
    'Green_Roof':     'SPGD_roof_green',
    'Pergola':        'SPGD_pergola',
    'Coffee':         'SPGD_coffee',
    'Running_Track':  'SPGD_track',
}

replaced = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    for i, slot in enumerate(obj.material_slots):
        if slot.material and slot.material.name in material_map:
            new_key = material_map[slot.material.name]
            if new_key in materials:
                slot.material = materials[new_key]
                replaced += 1

print(f"  Done: Replaced {replaced} material slots with PBR")

# ═══════════════════════════════════════════
# STEP 5: Bevel + Solidify all geometry
# ═══════════════════════════════════════════
print("[5/9] Adding bevel + solidify to all meshes...")

modified = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    if obj.name == "Ground_Terrain":
        continue

    # Skip if already has these modifiers
    has_bevel = any(m.type == 'BEVEL' for m in obj.modifiers)
    has_solidify = any(m.type == 'SOLIDIFY' for m in obj.modifiers)

    if not has_bevel:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_add(type='BEVEL')
        obj.modifiers['Bevel'].width = 0.015
        obj.modifiers['Bevel'].segments = 2
        obj.modifiers['Bevel'].limit_method = 'ANGLE'
        obj.modifiers['Bevel'].angle_limit = math.radians(30)

    # Only solidify thin objects (walls, roofs) not bulky ones
    dims = obj.dimensions
    min_dim = min(dims.x, dims.y, dims.z) if all(d > 0 for d in dims) else 1
    if not has_solidify and min_dim < 0.15 and min_dim > 0:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_add(type='SOLIDIFY')
        obj.modifiers['Solidify'].thickness = 0.12
        obj.modifiers['Solidify'].offset = -1

    modified += 1

print(f"  Done: Modified {modified} objects")

# ═══════════════════════════════════════════
# STEP 6: Fix floating objects
# ═══════════════════════════════════════════
print("[6/9] Fixing floating objects...")

fixed = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    if 'Speaker' in obj.name or 'Scr_' in obj.name or 'Screen' in obj.name:
        continue  # speakers/screens are intentionally elevated
    if 'Roof' in obj.name or 'Canopy' in obj.name:
        continue  # roofs are above walls
    if 'Camera' in obj.name or 'Light' in obj.name or 'Sun' in obj.name:
        continue

    # Check if object's lowest point is floating above 0.5m
    try:
        from mathutils import Vector
        bbox_world = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    except:
        bbox_world = []
    if bbox_world:
        min_z = min(v.z for v in bbox_world)
        if min_z > 0.5 and 'Post' not in obj.name:
            obj.location.z -= (min_z - 0.0)
            fixed += 1

print(f"  Done: Adjusted {fixed} floating objects")

# ═══════════════════════════════════════════
# STEP 7: Upgrade cameras
# ═══════════════════════════════════════════
print("[7/9] Setting up cameras...")

# Rename existing cameras
for obj in bpy.data.objects:
    if obj.type == 'CAMERA':
        if 'Aerial' in obj.name or 'aerial' in obj.name:
            obj.name = "CAM_aerial_overview"
            obj.data.type = 'ORTHO'
            obj.data.ortho_scale = 105
        elif 'Perspective' in obj.name or 'perspective' in obj.name:
            obj.name = "CAM_perspective_hero"
            obj.data.type = 'PERSP'
            obj.data.lens = 35
            obj.data.sensor_width = 36
            obj.data.clip_end = 500
        elif 'Entrance' in obj.name or 'entrance' in obj.name:
            obj.name = "CAM_entrance_approach"
            obj.data.type = 'PERSP'
            obj.data.lens = 35
            obj.data.sensor_width = 36
            obj.data.clip_end = 500

print("  Done: 3 cameras configured")

# ═══════════════════════════════════════════
# STEP 8: Upgrade sun light
# ═══════════════════════════════════════════
print("[8/9] Configuring sun light...")

for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        if obj.data.type == 'SUN':
            obj.data.energy = 3.0  # moderate, let exposure handle brightness
            obj.data.angle = math.radians(0.545)  # real sun angular diameter

print("  Done")

# ═══════════════════════════════════════════
# STEP 9: Render all 3 views
# ═══════════════════════════════════════════
print("[9/9] Rendering 3 views with Cycles...")

scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '16'

cameras = ['CAM_aerial_overview', 'CAM_perspective_hero', 'CAM_entrance_approach']

for cam_name in cameras:
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        print(f"  SKIP: {cam_name} not found")
        continue

    scene.camera = cam_obj
    out_path = os.path.join(RENDER_DIR, f"v5_{cam_name}.png")
    scene.render.filepath = out_path
    print(f"  Rendering {cam_name}...")
    bpy.ops.render.render(write_still=True)
    print(f"  Saved: {out_path}")

# Save the upgraded blend file
save_path = os.path.expanduser("~/Projects/sponic-garden-3d/sponic-garden-v5.blend")
bpy.ops.wm.save_as_mainfile(filepath=save_path)

print(f"\nAll done! Project saved to {save_path}")
print(f"Renders in {RENDER_DIR}/")
