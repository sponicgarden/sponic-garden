"""
Sponic Garden v11 — Blue Hour Renders
Loads the saved v11 .blend, sets sun below horizon for blue hour twilight.
String lights and fire pit glow become the primary light sources.

Usage: blender --background sponic-garden-v11.blend --python render_v11_bluehour.py
"""
import bpy
import math
import os
import time

print("=" * 60)
print("  v11 BLUE HOUR — 2 cameras, 2048spp")
print("=" * 60)

scene = bpy.context.scene
start = time.time()

# ═══════════════════════════════════════════
# BLUE HOUR LIGHTING — sun below horizon
# ═══════════════════════════════════════════

sun = bpy.data.objects.get("Sun")
if sun:
    sun.data.energy = 0.5  # very dim — just above horizon glow
    sun.data.color = (0.60, 0.55, 0.80)  # purple-blue
    sun.data.angle = math.radians(3.0)
    sun.rotation_euler = (math.radians(-2), math.radians(10), math.radians(-30))

fill = bpy.data.objects.get("Fill")
if fill:
    fill.data.energy = 0.3
    fill.data.color = (0.50, 0.55, 0.85)  # deep blue
    fill.rotation_euler = (math.radians(30), math.radians(-10), math.radians(150))

# Sky — twilight
world = scene.world
if world and world.use_nodes:
    for node in world.node_tree.nodes:
        if node.type == 'TEX_SKY':
            node.sun_elevation = math.radians(-3)  # below horizon
            node.sun_rotation = math.radians(-30)
            try:
                node.turbidity = 3.0
            except:
                pass
        elif node.type == 'BACKGROUND':
            node.inputs['Strength'].default_value = 0.6

# Exposure — bump up to compensate for dim scene
scene.view_settings.exposure = 1.2

# Boost string light and lantern energy for this mood
for obj in bpy.data.objects:
    if obj.type == 'LIGHT' and 'Glow' in obj.name:
        obj.data.energy *= 2.0  # string lights brighter
    elif obj.type == 'LIGHT' and '_L' in obj.name and 'Ln_' in obj.name:
        obj.data.energy *= 2.0  # lanterns brighter

# ═══════════════════════════════════════════
# RENDER SETTINGS
# ═══════════════════════════════════════════
scene.cycles.samples = 2048
scene.render.resolution_x = 2560
scene.render.resolution_y = 1440

# ═══════════════════════════════════════════
# RENDER 2 MOOD CAMERAS
# ═══════════════════════════════════════════
RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v11-bluehour")
os.makedirs(RENDER_DIR, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'

cam_names = [
    'CAM_firepit_evening',  # fire pit glow + string lights + blue sky
    'CAM_pool_spa',         # pool reflections + sauna window glow + blue
]

for ci, cam_name in enumerate(cam_names):
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        print(f"  WARNING: {cam_name} not found, skipping")
        continue

    scene.camera = cam_obj
    out_path = os.path.join(RENDER_DIR, f"v11_blue_{cam_name}.png")
    scene.render.filepath = out_path
    render_start = time.time()
    print(f"\n  [{ci+1}/{len(cam_names)}] Rendering {cam_name} (blue hour)...")
    bpy.ops.render.render(write_still=True)
    render_time = time.time() - render_start
    print(f"  Saved: {out_path} ({render_time:.0f}s)")

total = time.time() - start
print(f"\n{'=' * 60}")
print(f"  BLUE HOUR COMPLETE — {total/60:.1f} min")
print(f"  Output: {RENDER_DIR}/")
print(f"{'=' * 60}")
