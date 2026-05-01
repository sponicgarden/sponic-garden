-- 011_relations.sql
-- Relations CRM: 3 unified pipelines (fundraising, location partners, staff
-- recruiting) sharing one schema. Standard contact fields are columns; per-
-- pipeline custom fields live in a jsonb column whose shape is defined by the
-- parent pipeline's `custom_field_schema`. Stages are per-pipeline rows.
--
-- Backend is Claude-only: writes happen via service_role (SQL / scripts).
-- Frontend at /in/relations/ reads via the anon key, gated by Google OAuth +
-- the `site.admin_emails` allowlist (same pattern as admin/devcontrol.html).

-- ─── Admin-email helper ──────────────────────────────────────────────────────
-- Returns true if the current authenticated user's email is in
-- config.site.admin_emails. Used by all relations_* RLS policies.
CREATE OR REPLACE FUNCTION is_relations_admin() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT COALESCE(
    (auth.jwt() ->> 'email') IN (
      SELECT jsonb_array_elements_text(
        COALESCE((SELECT value::jsonb FROM config WHERE key = 'site.admin_emails'), '[]'::jsonb)
      )
    ),
    false
  )
$$;

-- ─── Pipelines ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS relations_pipelines (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                text NOT NULL UNIQUE,
  title               text NOT NULL,
  description         text,
  icon                text,
  display_order       integer NOT NULL DEFAULT 0,
  custom_field_schema jsonb NOT NULL DEFAULT '{"fields":[]}'::jsonb,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE relations_pipelines ENABLE ROW LEVEL SECURITY;
CREATE POLICY "relations_pipelines admin all"
  ON relations_pipelines FOR ALL
  USING (is_relations_admin())
  WITH CHECK (is_relations_admin());

-- ─── Stages (per pipeline) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS relations_stages (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id   uuid NOT NULL REFERENCES relations_pipelines(id) ON DELETE CASCADE,
  slug          text NOT NULL,
  title         text NOT NULL,
  description   text,
  display_order integer NOT NULL DEFAULT 0,
  color         text,
  terminal_kind text CHECK (terminal_kind IN ('won','lost')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pipeline_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_relations_stages_pipeline
  ON relations_stages (pipeline_id, display_order);

ALTER TABLE relations_stages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "relations_stages admin all"
  ON relations_stages FOR ALL
  USING (is_relations_admin())
  WITH CHECK (is_relations_admin());

-- ─── Contacts (unified across all pipelines) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS relations_contacts (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id         uuid NOT NULL REFERENCES relations_pipelines(id) ON DELETE RESTRICT,
  stage_id            uuid REFERENCES relations_stages(id) ON DELETE SET NULL,
  -- standard contact fields (shared across all 3 CRMs)
  name                text NOT NULL,
  email               text,
  phone               text,
  company             text,
  title               text,
  linkedin_url        text,
  website             text,
  city                text,
  country             text,
  notes               text,
  tags                text[] NOT NULL DEFAULT '{}',
  -- workflow fields
  owner_email         text,
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','archived')),
  priority            smallint NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
  expected_value      numeric,
  expected_close_date date,
  last_contacted_at   timestamptz,
  next_action_at      timestamptz,
  next_action_note    text,
  -- extensible per-pipeline fields (validated client-side against pipeline.custom_field_schema)
  custom              jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_relations_contacts_pipeline_stage
  ON relations_contacts (pipeline_id, stage_id);
CREATE INDEX IF NOT EXISTS idx_relations_contacts_pipeline_status
  ON relations_contacts (pipeline_id, status);
CREATE INDEX IF NOT EXISTS idx_relations_contacts_next_action
  ON relations_contacts (next_action_at) WHERE next_action_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_relations_contacts_tags
  ON relations_contacts USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_relations_contacts_custom
  ON relations_contacts USING GIN (custom);

ALTER TABLE relations_contacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "relations_contacts admin all"
  ON relations_contacts FOR ALL
  USING (is_relations_admin())
  WITH CHECK (is_relations_admin());

-- ─── Activities (append-only timeline) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS relations_activities (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id  uuid NOT NULL REFERENCES relations_contacts(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('note','email','call','meeting','stage_change','field_change','task','other')),
  body        text,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_relations_activities_contact
  ON relations_activities (contact_id, occurred_at DESC);

ALTER TABLE relations_activities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "relations_activities admin all"
  ON relations_activities FOR ALL
  USING (is_relations_admin())
  WITH CHECK (is_relations_admin());

-- ─── updated_at trigger ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION relations_set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

CREATE TRIGGER trg_relations_pipelines_updated BEFORE UPDATE ON relations_pipelines
  FOR EACH ROW EXECUTE FUNCTION relations_set_updated_at();
CREATE TRIGGER trg_relations_stages_updated BEFORE UPDATE ON relations_stages
  FOR EACH ROW EXECUTE FUNCTION relations_set_updated_at();
CREATE TRIGGER trg_relations_contacts_updated BEFORE UPDATE ON relations_contacts
  FOR EACH ROW EXECUTE FUNCTION relations_set_updated_at();

-- ─── Auto-log stage changes ──────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION relations_log_stage_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.stage_id IS DISTINCT FROM OLD.stage_id THEN
    INSERT INTO relations_activities (contact_id, kind, body, metadata, created_by)
    VALUES (
      NEW.id,
      'stage_change',
      NULL,
      jsonb_build_object('from_stage_id', OLD.stage_id, 'to_stage_id', NEW.stage_id),
      COALESCE(auth.jwt() ->> 'email', 'system')
    );
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_relations_contacts_stage_change AFTER UPDATE ON relations_contacts
  FOR EACH ROW EXECUTE FUNCTION relations_log_stage_change();

-- ═════════════════════════════════════════════════════════════════════════════
-- SEED: 3 pipelines + starter stages + example custom-field schemas
-- ═════════════════════════════════════════════════════════════════════════════

INSERT INTO relations_pipelines (slug, title, description, icon, display_order, custom_field_schema) VALUES
  ('fundraising', 'Fundraising', 'Investor pipeline — VCs, angels, family offices, strategic capital.', '💰', 1,
    '{"fields":[
      {"key":"check_size","label":"Check Size","type":"currency"},
      {"key":"thesis_fit","label":"Thesis Fit","type":"select","options":["A","B","C"]},
      {"key":"warm_intro_via","label":"Warm intro via","type":"text"},
      {"key":"fund_stage","label":"Fund Stage","type":"select","options":["pre-seed","seed","series-a","series-b","growth","strategic","family-office"]},
      {"key":"follow_on_capacity","label":"Follow-on capacity","type":"currency"},
      {"key":"deck_sent","label":"Deck sent","type":"boolean"},
      {"key":"data_room_access","label":"Data room access","type":"boolean"}
    ]}'::jsonb),
  ('location-partners', 'Location Partners', 'Site & operator pipeline — hotels, clubs, coworking, retail, restaurants.', '📍', 2,
    '{"fields":[
      {"key":"space_type","label":"Space type","type":"select","options":["hotel","club","coworking","restaurant","retail","gallery","other"]},
      {"key":"space_sqft","label":"Space (sqft)","type":"number"},
      {"key":"monthly_rate","label":"Monthly rate","type":"currency"},
      {"key":"available_from","label":"Available from","type":"date"},
      {"key":"foot_traffic","label":"Foot traffic / day","type":"number"},
      {"key":"audience_fit","label":"Audience fit","type":"select","options":["A","B","C"]},
      {"key":"site_visited","label":"Site visited","type":"boolean"}
    ]}'::jsonb),
  ('staff-recruiting', 'Staff Recruiting', 'Hiring pipeline — engineers, ops, design, biz dev, advisors.', '👥', 3,
    '{"fields":[
      {"key":"target_role","label":"Target role","type":"text"},
      {"key":"seniority","label":"Seniority","type":"select","options":["junior","mid","senior","staff","principal","exec","advisor"]},
      {"key":"comp_target","label":"Comp target","type":"currency"},
      {"key":"comp_offered","label":"Comp offered","type":"currency"},
      {"key":"start_date","label":"Earliest start","type":"date"},
      {"key":"referrer","label":"Referrer","type":"text"},
      {"key":"resume_url","label":"Resume URL","type":"url"}
    ]}'::jsonb)
ON CONFLICT (slug) DO NOTHING;

-- Fundraising stages
INSERT INTO relations_stages (pipeline_id, slug, title, display_order, color, terminal_kind)
SELECT p.id, s.slug, s.title, s.display_order, s.color, s.terminal_kind
FROM relations_pipelines p, (VALUES
  ('sourced',       'Sourced',       1, '#9ca3af', NULL),
  ('reached-out',   'Reached out',   2, '#a78bfa', NULL),
  ('pitch-sent',    'Pitch sent',    3, '#60a5fa', NULL),
  ('pitch-meeting', 'Pitch meeting', 4, '#3b82f6', NULL),
  ('diligence',     'Diligence',     5, '#f59e0b', NULL),
  ('term-sheet',    'Term sheet',    6, '#10b981', NULL),
  ('closed-won',    'Closed (won)',  7, '#059669', 'won'),
  ('passed',        'Passed',        8, '#6b7280', 'lost')
) AS s(slug, title, display_order, color, terminal_kind)
WHERE p.slug = 'fundraising'
ON CONFLICT (pipeline_id, slug) DO NOTHING;

-- Location partner stages
INSERT INTO relations_stages (pipeline_id, slug, title, display_order, color, terminal_kind)
SELECT p.id, s.slug, s.title, s.display_order, s.color, s.terminal_kind
FROM relations_pipelines p, (VALUES
  ('identified',   'Identified',     1, '#9ca3af', NULL),
  ('outreached',   'Outreached',     2, '#a78bfa', NULL),
  ('initial-call', 'Initial call',   3, '#60a5fa', NULL),
  ('site-visit',   'Site visit',     4, '#3b82f6', NULL),
  ('loi',          'LOI',            5, '#f59e0b', NULL),
  ('negotiation',  'Negotiation',    6, '#fb923c', NULL),
  ('signed',       'Signed',         7, '#059669', 'won'),
  ('declined',     'Declined',       8, '#6b7280', 'lost')
) AS s(slug, title, display_order, color, terminal_kind)
WHERE p.slug = 'location-partners'
ON CONFLICT (pipeline_id, slug) DO NOTHING;

-- Staff recruiting stages
INSERT INTO relations_stages (pipeline_id, slug, title, display_order, color, terminal_kind)
SELECT p.id, s.slug, s.title, s.display_order, s.color, s.terminal_kind
FROM relations_pipelines p, (VALUES
  ('sourced',       'Sourced',       1, '#9ca3af', NULL),
  ('outreached',    'Outreached',    2, '#a78bfa', NULL),
  ('screen',        'Screen',        3, '#60a5fa', NULL),
  ('interview-1',   'Interview 1',   4, '#3b82f6', NULL),
  ('interview-2',   'Interview 2',   5, '#2563eb', NULL),
  ('reference',     'References',    6, '#f59e0b', NULL),
  ('offer',         'Offer',         7, '#10b981', NULL),
  ('hired',         'Hired',         8, '#059669', 'won'),
  ('passed',        'Passed',        9, '#6b7280', 'lost'),
  ('withdrew',      'Withdrew',     10, '#6b7280', 'lost')
) AS s(slug, title, display_order, color, terminal_kind)
WHERE p.slug = 'staff-recruiting'
ON CONFLICT (pipeline_id, slug) DO NOTHING;
