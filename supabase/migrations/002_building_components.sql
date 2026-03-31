-- 002_building_components.sql
-- CAD-like component library for Blender scene assembly
-- Each row = a reusable building component with bpy creation script

CREATE TABLE IF NOT EXISTS spgd_building_components (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name            text NOT NULL,
  slug            text NOT NULL UNIQUE,
  category        text NOT NULL CHECK (category IN (
                    'structure', 'furniture', 'fixture', 'landscape', 'tech'
                  )),
  subcategory     text,
  description     text,
  dimensions_m    jsonb NOT NULL DEFAULT '{}'::jsonb,
  material_preset text,
  bpy_script      text NOT NULL,
  tags            text[] DEFAULT '{}',
  blender_version text DEFAULT '5.1',
  is_active       boolean NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_spgd_bc_category ON spgd_building_components (category);
CREATE INDEX IF NOT EXISTS idx_spgd_bc_subcategory ON spgd_building_components (subcategory);
CREATE INDEX IF NOT EXISTS idx_spgd_bc_tags ON spgd_building_components USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_spgd_bc_slug ON spgd_building_components (slug);

-- Helper function: returns bpy script with coordinates substituted
CREATE OR REPLACE FUNCTION place_component(
  p_slug text,
  p_x double precision DEFAULT 0,
  p_y double precision DEFAULT 0,
  p_z double precision DEFAULT 0,
  p_name_override text DEFAULT NULL
)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v_script text;
  v_name text;
BEGIN
  SELECT bpy_script, COALESCE(p_name_override, name)
    INTO v_script, v_name
    FROM spgd_building_components
   WHERE slug = p_slug AND is_active = true;

  IF v_script IS NULL THEN
    RAISE EXCEPTION 'Component not found: %', p_slug;
  END IF;

  -- Replace placeholders in script
  v_script := replace(v_script, '{{X}}', p_x::text);
  v_script := replace(v_script, '{{Y}}', p_y::text);
  v_script := replace(v_script, '{{Z}}', p_z::text);
  v_script := replace(v_script, '{{NAME}}', v_name);

  RETURN v_script;
END;
$$;

-- Seed: Structure components
INSERT INTO spgd_building_components (name, slug, category, subcategory, description, dimensions_m, material_preset, bpy_script, tags)
VALUES
-- BUILDING SHELLS
('Welcome Center', 'welcome-center-shell', 'structure', 'building',
 'Main entrance building with green roof. 10m x 8m x 4.5m.',
 '{"w": 10, "d": 8, "h": 4.5}'::jsonb,
 'SPGD_structure_steel_frame',
 $BPY$
import bpy, bmesh

def create_welcome_center(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    w, d, h, wt = 10.0, 8.0, 4.5, 0.2

    # Floor slab
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z - 0.1))
    floor = bpy.context.active_object
    floor.name = f"{name}_Floor"
    floor.scale = (w/2, d/2, 0.1)
    bpy.ops.object.modifier_add(type='BEVEL')
    floor.modifiers['Bevel'].width = 0.02
    floor.modifiers['Bevel'].segments = 3

    # Walls (4 sides with thickness via Solidify)
    for side, loc, sc in [
        ('S', (x, y - d/2 + wt/2, z + h/2), (w/2, wt/2, h/2)),
        ('N', (x, y + d/2 - wt/2, z + h/2), (w/2, wt/2, h/2)),
        ('W', (x - w/2 + wt/2, y, z + h/2), (wt/2, d/2, h/2)),
        ('E', (x + w/2 - wt/2, y, z + h/2), (wt/2, d/2, h/2)),
    ]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        wall = bpy.context.active_object
        wall.name = f"{name}_Wall_{side}"
        wall.scale = sc
        bpy.ops.object.modifier_add(type='BEVEL')
        wall.modifiers['Bevel'].width = 0.02
        wall.modifiers['Bevel'].segments = 3

    # Roof slab
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + h + 0.05))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof"
    roof.scale = (w/2 + 0.3, d/2 + 0.3, 0.08)
    bpy.ops.object.modifier_add(type='BEVEL')
    roof.modifiers['Bevel'].width = 0.03
    roof.modifiers['Bevel'].segments = 3

create_welcome_center()
$BPY$,
 '{building, entrance, welcome}'
),

('Greenhouse Frame', 'greenhouse-frame', 'structure', 'building',
 'Glass-walled greenhouse with glass roof. 20m x 15m x 5.5m.',
 '{"w": 20, "d": 15, "h": 5.5}'::jsonb,
 'SPGD_structure_glass_clear',
 $BPY$
import bpy

def create_greenhouse(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    w, d, h = 20.0, 15.0, 5.5
    gt = 0.08  # glass thickness

    # Concrete base/floor
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z - 0.15))
    floor = bpy.context.active_object
    floor.name = f"{name}_Floor"
    floor.scale = (w/2, d/2, 0.15)

    # Steel frame columns (8 columns around perimeter)
    for cx, cy in [(-w/2+0.5, -d/2+0.5), (0, -d/2+0.5), (w/2-0.5, -d/2+0.5),
                   (-w/2+0.5, d/2-0.5), (0, d/2-0.5), (w/2-0.5, d/2-0.5),
                   (-w/2+0.5, 0), (w/2-0.5, 0)]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x+cx, y+cy, z+h/2))
        col = bpy.context.active_object
        col.name = f"{name}_Column"
        col.scale = (0.06, 0.06, h/2)
        bpy.ops.object.modifier_add(type='BEVEL')
        col.modifiers['Bevel'].width = 0.01
        col.modifiers['Bevel'].segments = 2

    # Glass walls (thin panels)
    for side, loc, sc in [
        ('S', (x, y-d/2, z+h/2), (w/2, gt/2, h/2)),
        ('N', (x, y+d/2, z+h/2), (w/2, gt/2, h/2)),
        ('W', (x-w/2, y, z+h/2), (gt/2, d/2, h/2)),
        ('E', (x+w/2, y, z+h/2), (gt/2, d/2, h/2)),
    ]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        glass = bpy.context.active_object
        glass.name = f"{name}_Glass_{side}"
        glass.scale = sc

    # Glass roof
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z+h))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof_Glass"
    roof.scale = (w/2, d/2, gt/2)

create_greenhouse()
$BPY$,
 '{building, greenhouse, glass, growing}'
),

-- FIXTURES
('Hot Tub Round', 'hot-tub-round', 'fixture', 'spa',
 'Circular hot tub, 2.2m diameter, 0.9m deep with rim.',
 '{"diameter": 2.2, "h": 0.9}'::jsonb,
 'SPGD_fixture_hot_tub',
 $BPY$
import bpy

def create_hot_tub(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    r_outer, r_inner, depth = 1.1, 0.95, 0.9
    rim_h = 0.12

    # Outer shell
    bpy.ops.mesh.primitive_cylinder_add(radius=r_outer, depth=depth, location=(x, y, z + depth/2))
    shell = bpy.context.active_object
    shell.name = f"{name}_Shell"
    bpy.ops.object.modifier_add(type='BEVEL')
    shell.modifiers['Bevel'].width = 0.02
    shell.modifiers['Bevel'].segments = 4

    # Inner cavity (water surface)
    bpy.ops.mesh.primitive_cylinder_add(radius=r_inner, depth=0.02, location=(x, y, z + depth - rim_h))
    water = bpy.context.active_object
    water.name = f"{name}_Water"

    # Rim
    bpy.ops.mesh.primitive_torus_add(major_radius=r_outer - 0.05, minor_radius=0.06,
                                      location=(x, y, z + depth))
    rim = bpy.context.active_object
    rim.name = f"{name}_Rim"

create_hot_tub()
$BPY$,
 '{spa, water, thermal}'
),

('Cold Plunge Pool', 'cold-plunge-rect', 'fixture', 'spa',
 'Rectangular cold plunge, 2m x 3m x 1.2m deep.',
 '{"w": 2, "d": 3, "h": 1.2}'::jsonb,
 'SPGD_landscape_water_pool',
 $BPY$
import bpy

def create_cold_plunge(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    w, d, depth, wt = 2.0, 3.0, 1.2, 0.1

    # Outer shell
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + depth/2))
    shell = bpy.context.active_object
    shell.name = f"{name}_Shell"
    shell.scale = (w/2, d/2, depth/2)
    bpy.ops.object.modifier_add(type='SOLIDIFY')
    shell.modifiers['Solidify'].thickness = wt
    shell.modifiers['Solidify'].offset = -1
    bpy.ops.object.modifier_add(type='BEVEL')
    shell.modifiers['Bevel'].width = 0.015
    shell.modifiers['Bevel'].segments = 3

    # Water surface
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, z + depth - 0.05))
    water = bpy.context.active_object
    water.name = f"{name}_Water"
    water.scale = ((w - wt*2)/2, (d - wt*2)/2, 1)

create_cold_plunge()
$BPY$,
 '{spa, water, cold, thermal}'
),

('Sauna Room', 'sauna-room', 'fixture', 'spa',
 'Cedar sauna cabin, 3m x 4m x 2.4m with bench.',
 '{"w": 3, "d": 4, "h": 2.4}'::jsonb,
 'SPGD_fixture_sauna_cedar',
 $BPY$
import bpy

def create_sauna(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    w, d, h, wt = 3.0, 4.0, 2.4, 0.12

    # Walls
    for side, loc, sc in [
        ('S', (x, y-d/2+wt/2, z+h/2), (w/2, wt/2, h/2)),
        ('N', (x, y+d/2-wt/2, z+h/2), (w/2, wt/2, h/2)),
        ('W', (x-w/2+wt/2, y, z+h/2), (wt/2, d/2, h/2)),
        ('E', (x+w/2-wt/2, y, z+h/2), (wt/2, d/2, h/2)),
    ]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        wall = bpy.context.active_object
        wall.name = f"{name}_Wall_{side}"
        wall.scale = sc
        bpy.ops.object.modifier_add(type='BEVEL')
        wall.modifiers['Bevel'].width = 0.01
        wall.modifiers['Bevel'].segments = 2

    # Roof
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z+h+0.06))
    roof = bpy.context.active_object
    roof.name = f"{name}_Roof"
    roof.scale = (w/2+0.1, d/2+0.1, 0.06)

    # Bench (L-shaped)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x-w/2+0.6, y, z+0.45))
    bench = bpy.context.active_object
    bench.name = f"{name}_Bench"
    bench.scale = (0.35, d/2-0.3, 0.04)

create_sauna()
$BPY$,
 '{spa, sauna, thermal, cedar}'
),

-- LANDSCAPE
('Raised Garden Bed', 'raised-garden-bed', 'landscape', 'garden',
 'Timber raised bed, 3.2m x 1.4m x 0.5m with soil fill.',
 '{"w": 3.2, "d": 1.4, "h": 0.5}'::jsonb,
 'SPGD_landscape_soil_bed',
 $BPY$
import bpy

def create_raised_bed(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    w, d, h, wt = 3.2, 1.4, 0.5, 0.05

    # Timber frame
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z+h/2))
    frame = bpy.context.active_object
    frame.name = f"{name}_Frame"
    frame.scale = (w/2, d/2, h/2)
    bpy.ops.object.modifier_add(type='SOLIDIFY')
    frame.modifiers['Solidify'].thickness = wt
    frame.modifiers['Solidify'].offset = -1
    bpy.ops.object.modifier_add(type='BEVEL')
    frame.modifiers['Bevel'].width = 0.008
    frame.modifiers['Bevel'].segments = 2

    # Soil fill
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z+h-0.03))
    soil = bpy.context.active_object
    soil.name = f"{name}_Soil"
    soil.scale = ((w-wt*2)/2, (d-wt*2)/2, 0.02)

create_raised_bed()
$BPY$,
 '{garden, growing, outdoor}'
),

('Fire Pit Ring', 'fire-pit-ring', 'landscape', 'gathering',
 'Stone fire pit, 1.2m diameter with seating ring.',
 '{"diameter": 1.2, "h": 0.4, "seating_diameter": 4.5}'::jsonb,
 'SPGD_structure_concrete_floor',
 $BPY$
import bpy

def create_fire_pit(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    # Fire ring (stone)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=0.4, location=(x, y, z+0.2))
    ring = bpy.context.active_object
    ring.name = f"{name}_Ring"
    bpy.ops.object.modifier_add(type='SOLIDIFY')
    ring.modifiers['Solidify'].thickness = 0.12
    ring.modifiers['Solidify'].offset = -1
    bpy.ops.object.modifier_add(type='BEVEL')
    ring.modifiers['Bevel'].width = 0.02
    ring.modifiers['Bevel'].segments = 3

    # Seating circle (wood bench ring)
    bpy.ops.mesh.primitive_torus_add(major_radius=2.25, minor_radius=0.2,
                                      location=(x, y, z+0.35))
    seat = bpy.context.active_object
    seat.name = f"{name}_Seating"

create_fire_pit()
$BPY$,
 '{gathering, outdoor, fire}'
),

-- TECH
('Wall-Mounted Screen', 'screen-wall-mounted', 'tech', 'display',
 'Flat display, 1.2m x 0.7m, wall-mountable with bezel.',
 '{"w": 1.2, "d": 0.05, "h": 0.7}'::jsonb,
 'SPGD_tech_screen',
 $BPY$
import bpy

def create_screen(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    # Bezel frame
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    frame = bpy.context.active_object
    frame.name = f"{name}_Frame"
    frame.scale = (0.62, 0.025, 0.37)
    bpy.ops.object.modifier_add(type='BEVEL')
    frame.modifiers['Bevel'].width = 0.005
    frame.modifiers['Bevel'].segments = 2

    # Screen surface (emissive)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y-0.026, z))
    screen = bpy.context.active_object
    screen.name = f"{name}_Display"
    screen.scale = (0.58, 0.34, 1)
    screen.rotation_euler = (1.5708, 0, 0)

create_screen()
$BPY$,
 '{display, screen, indoor, outdoor}'
),

('Outdoor Speaker', 'speaker-outdoor', 'tech', 'audio',
 'Weatherproof speaker housing, 0.2m x 0.2m x 0.3m.',
 '{"w": 0.2, "d": 0.2, "h": 0.3}'::jsonb,
 'SPGD_tech_speaker',
 $BPY$
import bpy

def create_speaker(x={{X}}, y={{Y}}, z={{Z}}, name="{{NAME}}"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    spk = bpy.context.active_object
    spk.name = name
    spk.scale = (0.1, 0.1, 0.15)
    bpy.ops.object.modifier_add(type='BEVEL')
    spk.modifiers['Bevel'].width = 0.01
    spk.modifiers['Bevel'].segments = 3

create_speaker()
$BPY$,
 '{audio, speaker, outdoor, indoor}'
)

ON CONFLICT (slug) DO UPDATE SET
  bpy_script = EXCLUDED.bpy_script,
  dimensions_m = EXCLUDED.dimensions_m,
  material_preset = EXCLUDED.material_preset,
  updated_at = now();
