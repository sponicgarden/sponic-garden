"""
Sponic Garden v11 — New Camera Angles
Loads the saved v11 .blend, restores daylight, adds 4 new cameras
for angles the original 8 don't cover.

Usage: blender --background sponic-garden-v11.blend --python render_v11_newcams.py
"""
import bpy
import math
import os
import time

print("=" * 60)
print("  v11 NEW CAMERAS — 4 angles, 2048spp, daylight")
print("=" * 60)

scene = bpy.context.scene
start = time.time()

# ═══════════════════════════════════════════
# RESTORE DAYLIGHT (undo golden hour if it ran before this)
# ═══════════════════════════════════════════
sun = bpy.data.objects.get("Sun")
if sun:
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.97, 0.92)
    sun.data.angle = math.radians(0.5)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))

fill = bpy.data.objects.get("Fill")
if fill:
    fill.data.energy = 1.5
    fill.data.color = (0.90, 0.92, 1.0)
    fill.rotation_euler = (math.radians(55), math.radians(-10), math.radians(150))

world = scene.world
if world and world.use_nodes:
    for node in world.node_tree.nodes:
        if node.type == 'TEX_SKY':
            node.sun_elevation = math.radians(50)
            node.sun_rotation = math.radians(-30)
            try:
                node.turbidity = 2.0
            except:
                pass
        elif node.type == 'BACKGROUND':
            node.inputs['Strength'].default_value = 1.2

scene.view_settings.exposure = 0.3

# ═══════════════════════════════════════════
# RENDER SETTINGS
# ═══════════════════════════════════════════
scene.cycles.samples = 2048
scene.render.resolution_x = 2560
scene.render.resolution_y = 1440

# ═══════════════════════════════════════════
# ADD 4 NEW CAMERAS
# ═══════════════════════════════════════════

# Scene coordinates reference:
# Greenhouse: (0, 25), Dining: (-22, 8), Education: (22, 10)
# Maker: (-22, -8), Movement: (22, -8), Welcome: (0, -18)
# SpaHouse: (12, -28), Pool: (-8, -32), Spa deck: (22, -28)
# Garden beds: (-38 to -18, 20 to 33), Fire pit: (-24, -24)

new_cams = []

# 1. CAM_greenhouse_interior — inside greenhouse looking south through glass
bpy.ops.object.camera_add(location=(0, 28, 2.5))
cam = bpy.context.active_object
cam.name = "CAM_greenhouse_interior"
cam.data.lens = 20  # ultra-wide to capture interior
cam.data.sensor_width = 36
cam.data.clip_end = 500
cam.rotation_euler = (math.radians(85), 0, math.radians(180))  # looking south
new_cams.append(cam.name)

# 2. CAM_garden_ground — ground level among garden beds looking toward greenhouse
bpy.ops.object.camera_add(location=(-28, 24, 0.8))
cam = bpy.context.active_object
cam.name = "CAM_garden_ground"
cam.data.lens = 24
cam.data.sensor_width = 36
cam.data.clip_end = 500
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 2.0
cam.data.dof.focus_distance = 4.0
# Look toward greenhouse at (0, 25)
cam.rotation_euler = (math.radians(88), 0, math.radians(-80))
new_cams.append(cam.name)

# 3. CAM_walkway — standing on covered walkway looking down its length
# Walkway WK1 runs from (-4, -14) to (-15, 3)
bpy.ops.object.camera_add(location=(-5, -12, 2.0))
cam = bpy.context.active_object
cam.name = "CAM_walkway"
cam.data.lens = 28
cam.data.sensor_width = 36
cam.data.clip_end = 500
# Look along walkway toward Dining Hall
cam.rotation_euler = (math.radians(82), 0, math.radians(-55))
new_cams.append(cam.name)

# 4. CAM_sauna_eyelevel — eye level at spa, focused on square saunas
# Saunas at (SX-3, SY+2)=(19, -26) and (SX+3, SY+2)=(25, -26)
bpy.ops.object.camera_add(location=(22, -32, 1.7))
cam = bpy.context.active_object
cam.name = "CAM_sauna_eyelevel"
cam.data.lens = 35
cam.data.sensor_width = 36
cam.data.clip_end = 500
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 2.8
# Focus on sauna 1 center
dx, dy, dz = 19 - 22, -26 - (-32), 1.2 - 1.7
cam.data.dof.focus_distance = math.sqrt(dx**2 + dy**2 + dz**2)
cam.rotation_euler = (math.radians(82), 0, math.radians(175))
new_cams.append(cam.name)

print(f"  Added {len(new_cams)} new cameras")

# ═══════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════
RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v11-newcams")
os.makedirs(RENDER_DIR, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'

for ci, cam_name in enumerate(new_cams):
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        print(f"  WARNING: {cam_name} not found, skipping")
        continue

    scene.camera = cam_obj
    out_path = os.path.join(RENDER_DIR, f"v11_{cam_name}.png")
    scene.render.filepath = out_path
    render_start = time.time()
    print(f"\n  [{ci+1}/{len(new_cams)}] Rendering {cam_name}...")
    bpy.ops.render.render(write_still=True)
    render_time = time.time() - render_start
    print(f"  Saved: {out_path} ({render_time:.0f}s)")

total = time.time() - start
print(f"\n{'=' * 60}")
print(f"  NEW CAMERAS COMPLETE — {total/60:.1f} min")
print(f"  Output: {RENDER_DIR}/")
print(f"{'=' * 60}")
