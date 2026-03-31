"""
Sponic Garden v11 — Geometry Passes Render
Loads the saved v11 .blend file and renders all 8 cameras with
depth, normal, mist, and AO passes at 128 samples (fast).
These passes are noise-free at low sample counts and provide
structural cues for Gemini AI enhancement.

Usage: blender --background sponic-garden-v11.blend --python render_v11_passes.py
"""
import bpy
import os
import time

print("=" * 60)
print("  v11 GEOMETRY PASSES — 128spp (fast)")
print("=" * 60)

scene = bpy.context.scene
start = time.time()

# ═══════════════════════════════════════════
# ENABLE PASSES on the active view layer
# ═══════════════════════════════════════════
vl = scene.view_layers[0]
vl.use_pass_z = True                    # Depth
vl.use_pass_normal = True               # World-space normals
vl.use_pass_mist = True                 # Distance falloff (0-1)
vl.use_pass_ambient_occlusion = True    # Contact shadows

# Mist settings — 0 to 100m falloff
scene.world.mist_settings.start = 0
scene.world.mist_settings.depth = 100
scene.world.mist_settings.falloff = 'QUADRATIC'

# ═══════════════════════════════════════════
# RENDER SETTINGS — fast, passes only need low samples
# ═══════════════════════════════════════════
scene.cycles.samples = 128
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.01

# Keep resolution same as v11
scene.render.resolution_x = 2560
scene.render.resolution_y = 1440

# ═══════════════════════════════════════════
# COMPOSITOR — output each pass to separate file
# ═══════════════════════════════════════════
# Enable compositing — Blender 5.x API
try:
    scene.use_nodes = True
except:
    pass

# Get compositor node tree (Blender 5.1+ uses scene.node_tree or bpy.context.scene.node_tree)
try:
    tree = scene.node_tree
except AttributeError:
    # Blender 5.1+: compositor is accessed via the nodetree directly
    bpy.ops.scene.new(type='EMPTY')
    scene.use_nodes = True
    tree = bpy.context.scene.node_tree

if tree is None:
    # Fallback: skip compositor, just render beauty with passes enabled
    print("  WARNING: Cannot access compositor node tree. Rendering beauty only with passes enabled.")
    # We'll save passes via view layer output instead
else:
    # Clear default nodes
    for node in tree.nodes:
        tree.nodes.remove(node)

    # Render Layers node
    rl_node = tree.nodes.new('CompositorNodeRLayers')
    rl_node.location = (0, 0)

    # Composite output (required)
    comp = tree.nodes.new('CompositorNodeComposite')
    comp.location = (600, 200)
    tree.links.new(rl_node.outputs['Image'], comp.inputs['Image'])

# ═══════════════════════════════════════════
# RENDER EACH CAMERA
# ═══════════════════════════════════════════
RENDER_DIR = os.path.expanduser("~/Projects/sponic-garden-3d/renders/v11-passes")
os.makedirs(RENDER_DIR, exist_ok=True)

cam_names = [
    'CAM_aerial', 'CAM_hero', 'CAM_pool_spa', 'CAM_entrance',
    'CAM_greenhouse_detail', 'CAM_firepit_evening', 'CAM_coffee_bar', 'CAM_spa_detail',
]

scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'

# For each camera, render and manually save passes
for ci, cam_name in enumerate(cam_names):
    cam_obj = bpy.data.objects.get(cam_name)
    if not cam_obj:
        print(f"  WARNING: {cam_name} not found, skipping")
        continue

    scene.camera = cam_obj

    # Set up file output nodes for this camera
    # Remove old file output nodes
    for node in list(tree.nodes):
        if node.type == 'OUTPUT_FILE':
            tree.nodes.remove(node)

    # Depth pass — normalize to 0-1 range
    norm = tree.nodes.new('CompositorNodeNormalize')
    norm.location = (300, -100)
    tree.links.new(rl_node.outputs['Depth'], norm.inputs[0])

    fo_depth = tree.nodes.new('CompositorNodeOutputFile')
    fo_depth.location = (600, -100)
    fo_depth.base_path = RENDER_DIR
    fo_depth.file_slots[0].path = f"v11_{cam_name}_depth_"
    tree.links.new(norm.outputs[0], fo_depth.inputs[0])

    # Normal pass
    fo_normal = tree.nodes.new('CompositorNodeOutputFile')
    fo_normal.location = (600, -300)
    fo_normal.base_path = RENDER_DIR
    fo_normal.file_slots[0].path = f"v11_{cam_name}_normal_"
    tree.links.new(rl_node.outputs['Normal'], fo_normal.inputs[0])

    # Mist pass
    fo_mist = tree.nodes.new('CompositorNodeOutputFile')
    fo_mist.location = (600, -500)
    fo_mist.base_path = RENDER_DIR
    fo_mist.file_slots[0].path = f"v11_{cam_name}_mist_"
    tree.links.new(rl_node.outputs['Mist'], fo_mist.inputs[0])

    # AO pass
    fo_ao = tree.nodes.new('CompositorNodeOutputFile')
    fo_ao.location = (600, -700)
    fo_ao.base_path = RENDER_DIR
    fo_ao.file_slots[0].path = f"v11_{cam_name}_ao_"
    tree.links.new(rl_node.outputs['AO'], fo_ao.inputs[0])

    # Render
    render_start = time.time()
    print(f"\n  [{ci+1}/{len(cam_names)}] Rendering passes for {cam_name}...")
    scene.render.filepath = os.path.join(RENDER_DIR, f"v11_{cam_name}_beauty_")
    bpy.ops.render.render(write_still=True)
    render_time = time.time() - render_start
    print(f"  Done ({render_time:.0f}s)")

    # Clean up normalize node for next camera
    tree.nodes.remove(norm)

total = time.time() - start
print(f"\n{'=' * 60}")
print(f"  GEOMETRY PASSES COMPLETE — {total/60:.1f} min")
print(f"  Output: {RENDER_DIR}/")
print(f"{'=' * 60}")
