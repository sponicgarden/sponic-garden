"""
Sponic Garden v11 — Golden Hour Renders
Loads the saved v11 .blend and re-renders 5 priority cameras
with golden hour sunset lighting. Same 2048spp quality.

Usage: blender --background sponic-garden-v11.blend --python render_v11_golden.py
"""
import bpy
import math
import os
import time

print("=" * 60)
print("  v11 GOLDEN HOUR — 5 cameras, 2048spp")
print("=" * 60)

scene = bpy.context.scene
start = time.time()

# ═══════════════════════════════════════════
# GOLDEN HOUR LIGHTING
# ═══════════════════════════════════════════

# Key sun — warm low sun
sun = bpy.data.objects.get("Sun")
if sun:
    sun.data.energy = 3.0
    sun.data.color = (1.0, 0.72, 0.42)  # warm orange
    sun.data.angle = math.radians(1.5)   # slightly larger for softer shadows
    sun.rotation_euler = (math.radians(12), math.radians(10), math.radians(-45))

# Fill — cooler blue to complement golden sun
fill = bpy.data.objects.get("Fill")
if fill:
    fill.data.energy = 0.8
    fill.data.color = (0.70, 0.75, 1.0)  # cool blue
    fill.rotation_euler = (math.radians(45), math.radians(-15), math.radians(160))

# Sky — lower sun, hazier
world = scene.world
if world and world.use_nodes:
    for node in world.node_tree.nodes:
        if node.type == 'TEX_SKY':
            node.sun_elevation = math.radians(12)
            node.sun_rotation = math.radians(-45)
            try:
                node.turbidity = 4.0  # hazier golden sky
            except:
                pass
        elif node.type == 'BACKGROUND':
            node.inputs['Strength'].default_value = 1.0  # slightly dimmer sky

# Exposure — compensate for low sun
scene.view_settings.exposure = 0.6

# ═══════════════════════════════════════════
# RENDER SETTINGS — same quality as v11
# ═══════════════════════════════════════════
scene.cycles.samples = 2048
scene.render.resolution_x = 2560
scene.render.resolution_y = 1440

# ═══════════════════════════════════════════
# RENDER 5 PRIORITY CAMERAS
# ═══════════════════════════════════════════
RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v11-golden")
os.makedirs(RENDER_DIR, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'

# Cameras that benefit most from golden hour
cam_names = [
    'CAM_hero',             # flagship shot
    'CAM_entrance',         # warm welcome
    'CAM_pool_spa',         # golden water reflections
    'CAM_firepit_evening',  # natural evening companion
    'CAM_coffee_bar',       # warm inviting atmosphere
]

for ci, cam_name in enumerate(cam_names):
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        print(f"  WARNING: {cam_name} not found, skipping")
        continue

    scene.camera = cam_obj
    out_path = os.path.join(RENDER_DIR, f"v11_golden_{cam_name}.png")
    scene.render.filepath = out_path
    render_start = time.time()
    print(f"\n  [{ci+1}/{len(cam_names)}] Rendering {cam_name} (golden hour)...")
    bpy.ops.render.render(write_still=True)
    render_time = time.time() - render_start
    print(f"  Saved: {out_path} ({render_time:.0f}s)")

total = time.time() - start
print(f"\n{'=' * 60}")
print(f"  GOLDEN HOUR COMPLETE — {total/60:.1f} min")
print(f"  Output: {RENDER_DIR}/")
print(f"{'=' * 60}")
