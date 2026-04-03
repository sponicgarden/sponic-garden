-- DevControl tables: context snapshots, backup logs, todo/planlist
-- Used by admin/devcontrol.html

-- Context window token snapshots (daily)
CREATE TABLE IF NOT EXISTS context_snapshots (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  snapshot_date date NOT NULL UNIQUE,
  always_loaded_tokens integer NOT NULL DEFAULT 0,
  total_tokens integer NOT NULL DEFAULT 0,
  breakdown jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

ALTER TABLE context_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read context_snapshots" ON context_snapshots FOR SELECT USING (true);
CREATE POLICY "Allow anon insert context_snapshots" ON context_snapshots FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anon update context_snapshots" ON context_snapshots FOR UPDATE USING (true);

-- Backup logs
CREATE TABLE IF NOT EXISTS backup_logs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  backup_type text NOT NULL DEFAULT 'full-to-rvault',
  status text NOT NULL DEFAULT 'success',
  duration_seconds integer,
  details jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

ALTER TABLE backup_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read backup_logs" ON backup_logs FOR SELECT USING (true);
CREATE POLICY "Allow anon insert backup_logs" ON backup_logs FOR INSERT WITH CHECK (true);

-- PlanList categories
CREATE TABLE IF NOT EXISTS todo_categories (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  title text NOT NULL,
  icon_svg text,
  display_order integer NOT NULL DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE todo_categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read todo_categories" ON todo_categories FOR SELECT USING (true);
CREATE POLICY "Allow anon insert todo_categories" ON todo_categories FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anon update todo_categories" ON todo_categories FOR UPDATE USING (true);
CREATE POLICY "Allow anon delete todo_categories" ON todo_categories FOR DELETE USING (true);

-- PlanList items
CREATE TABLE IF NOT EXISTS todo_items (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  category_id uuid NOT NULL REFERENCES todo_categories(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text,
  badge text,
  is_checked boolean NOT NULL DEFAULT false,
  checked_by uuid,
  checked_at timestamptz,
  display_order integer NOT NULL DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE todo_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read todo_items" ON todo_items FOR SELECT USING (true);
CREATE POLICY "Allow anon insert todo_items" ON todo_items FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anon update todo_items" ON todo_items FOR UPDATE USING (true);
CREATE POLICY "Allow anon delete todo_items" ON todo_items FOR DELETE USING (true);
