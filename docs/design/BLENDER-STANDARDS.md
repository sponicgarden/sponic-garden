# Sponic Garden -- Blender Design Standards

> Standard procedures for all 3D venue design work. Every render must pass the quality checklist before export.

## 1. Render Engine

| Setting | Value | bpy Path |
|---------|-------|----------|
| Engine | **Cycles** (never EEVEE for final) | `scene.render.engine = 'CYCLES'` |
| Device | Metal (M4 GPU) | `prefs.addons['cycles'].preferences.compute_device_type = 'METAL'` |
| Samples | 2048 (preview: 128) | `scene.cycles.samples = 2048` |
| Adaptive sampling | ON, threshold 0.01 | `scene.cycles.use_adaptive_sampling = True` |
| Denoiser | OIDN (OpenImageDenoise) | `scene.cycles.use_denoising = True` |
| Color mgmt | **AgX** (not Filmic, not Standard) | `scene.view_settings.view_transform = 'AgX'` |
| Look | Punchy | `scene.view_settings.look = 'AgX - Punchy'` |
| Resolution (hero) | 3840x2160 | `scene.render.resolution_x = 3840` |
| Resolution (working) | 1920x1080 | `scene.render.resolution_x = 1920` |
| Output | PNG 16-bit (compositing), JPG 90% (web) | |
| Tile size | 256x256 (Metal) | `scene.cycles.tile_size = 256` |

## 2. Materials (PBR Standard)

### Naming Convention
```
SPGD_{category}_{name}
```
Examples: `SPGD_structure_cedar_wall`, `SPGD_landscape_grass_lawn`

### Required Maps
Every material MUST have:
- **Base Color** (albedo)
- **Roughness**
- **Normal Map** (minimum)
- **Displacement** (for hero close-ups, use Micro-displacement with Adaptive Subdivision)

### Texture Sources (CC0 only)
- [ambientCG.com](https://ambientcg.com) -- PBR texture sets
- [Poly Haven](https://polyhaven.com/textures) -- textures + HDRIs
- Procedural Noise/Voronoi nodes for quick iteration

### Material Presets

| Preset | Base Color | Roughness | Notes |
|--------|-----------|-----------|-------|
| `SPGD_structure_steel_frame` | #505055 | 0.3 | Metallic: 0.9 |
| `SPGD_structure_concrete_floor` | #9E9A95 | 0.9 | Normal map essential |
| `SPGD_structure_cedar_wall` | #8C6239 | 0.7 | Warm brown, wood grain |
| `SPGD_structure_glass_clear` | #C0E8DB | 0.05 | Alpha: 0.15, IOR: 1.52 |
| `SPGD_landscape_grass_lawn` | #2D6B1E | 0.85 | Noise variation for realism |
| `SPGD_landscape_gravel_path` | #9E8E7E | 0.95 | Displacement for texture |
| `SPGD_landscape_soil_bed` | #5C4033 | 0.92 | Dark earth tone |
| `SPGD_landscape_water_pool` | #1A5C78 | 0.05 | Glass BSDF, slight green tint |
| `SPGD_fixture_sauna_cedar` | #9A6B3A | 0.65 | Warm golden wood |
| `SPGD_fixture_hot_tub` | #E8E4DE | 0.4 | Light fiberglass shell |
| `SPGD_tech_screen` | #0A0A0D | 0.1 | Emission: 2.0 for active screen |
| `SPGD_tech_speaker` | #1A1A1A | 0.7 | Matte black |

## 3. Lighting

### Outdoor Scenes
- **World shader:** Nishita Sky Texture (primary sun source)
  - Sun elevation: 45-60 degrees ("golden afternoon")
  - Sun rotation: -30 degrees (west-facing light)
  - Air density: 1.0, Dust density: 0.5
- **HDRI overlay** (optional): Poly Haven outdoor HDRI for ambient fill
  - Recommended: `kloofendal_48d_partly_cloudy_4k.hdr`
- **Exposure control:** Use `scene.view_settings.exposure` (range: -1 to +2)
  - NEVER crank lamp intensity above 10.0; adjust exposure instead
- **No point lights** for outdoor scenes (sun + HDRI only)

### Interior Scenes
- Area lights at window positions
- Color temperature: 4500K (warm)
- Bounce light from ground/walls via Cycles GI

## 4. Modeling Rules

### Scale
- **1 Blender Unit = 1 meter** (always)
- Apply scale (`Ctrl+A > Scale`) before any export or render

### Geometry Quality
| Rule | Why | How |
|------|-----|-----|
| Bevel ALL edges | Sharp 90-degree edges don't exist in reality; bevels catch specular highlights | Bevel modifier: width 0.02m, segments 3 |
| Wall thickness >= 0.15m | Single-face walls are invisible from angles and look fake | Solidify modifier: thickness 0.15-0.30m |
| Ground contact required | Floating objects break immersion instantly | Raycast snap, or manually verify Z-min = 0 |
| Support all canopies | Roofs/covers must have visible columns | Minimum 4 posts per covered structure |
| No intersecting geometry | Overlapping faces cause Z-fighting artifacts | Boolean union or manual separation |

### Object Origins
- Origin at **base center** of object (bottom face center)
- This ensures Z=0 means "sitting on ground"

## 5. Camera Conventions

### Naming
```
CAM_{view}_{purpose}
```

### Required Cameras (every project file)
| Camera | Focal Length | Type | Purpose |
|--------|-------------|------|---------|
| `CAM_aerial_overview` | N/A | Orthographic (scale: 105) | Top-down site plan |
| `CAM_perspective_hero` | 35mm | Perspective | 3/4 marketing shot |
| `CAM_entrance_approach` | 35mm | Perspective | Visitor's first view |
| `CAM_detail_*` | 50mm | Perspective, DOF f/2.8 | Close-up details |

### Settings
- Sensor size: 36mm (Full Frame equivalent)
- Clip start: 0.1m, Clip end: 500m
- Depth of field: ON for hero shots (aperture f/2.8), OFF for orthographic

## 6. Collection Hierarchy

```
Scene Collection
  Site
    Ground (terrain, ground plane)
    Buildings
      Welcome_Center
        Structure (walls, floor, roof)
        Interior (furniture, fixtures)
      Greenhouse
        Structure
        Interior
      Dining_Hall
        ...
      Education_Pavilion
      Maker_Studio
      Movement_Studio
      Spa_House
      Coffee_Bar
    Landscape
      Garden_Beds
      Orchard
      Paths
      Water_Features
    Infrastructure
      Walkways
      Tech_Overlay (speakers, screens, sensors)
    Cameras
    Lighting
```

## 7. Quality Checklist

**Run before EVERY final render:**

- [ ] No floating objects (orbit scene, check from 4 cardinal directions)
- [ ] All edges beveled (Bevel modifier on every mesh object)
- [ ] All walls have thickness (Solidify modifier, >= 0.15m)
- [ ] Every visible surface has a PBR material assigned
- [ ] HDRI or Nishita sky background loaded (no gray void)
- [ ] Ground plane extends beyond camera frustum edges
- [ ] Cycles selected (NOT EEVEE)
- [ ] AgX color management set (NOT Filmic or Standard)
- [ ] OIDN denoiser enabled
- [ ] Camera named with `CAM_` prefix and purpose
- [ ] Scale applied on all objects (`Ctrl+A > Scale`)
- [ ] Render resolution set (1920x1080 min for working, 3840x2160 for hero)
- [ ] Output path configured and directory exists

## 8. Post-Processing (Compositor)

For that final 5% of realism:
- **Glare node** (type: Fog Glow, threshold: 2.0, quality: High) -- soft bloom on bright areas
- **Lens Distortion** (dispersion: 0.01) -- subtle chromatic aberration
- **Vignette** (Ellipse Mask + Mix node, factor: 0.15) -- draws eye to center

## 9. Execution

### Headless render command
```bash
ssh paca@192.168.1.200 '/Applications/Blender.app/Contents/MacOS/Blender \
  --background ~/Projects/sponic-garden-3d/sponic-garden-v5.blend \
  --python ~/Projects/sponic-garden-3d/scripts/render_production.py \
  --render-output ~/Projects/sponic-garden-3d/renders/v5/ \
  --render-frame 1'
```

### Render time estimates (Mac mini M4, 1920x1080, 2048 samples)
| Scene complexity | Est. time |
|-----------------|-----------|
| Simple (< 100K tris) | 2-5 min |
| Medium (100K-500K tris) | 5-15 min |
| Complex (500K+ tris) | 15-45 min |
