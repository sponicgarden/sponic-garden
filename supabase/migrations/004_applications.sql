-- Applications table — stores AI interview conversations from the Work With Us page
create table if not exists applications (
  id          uuid primary key default gen_random_uuid(),
  role        text not null,
  email       text,
  name        text,
  summary     text,
  transcript  jsonb default '[]'::jsonb,
  status      text default 'submitted',
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- RLS: anonymous users can insert applications but cannot read them
alter table applications enable row level security;

create policy "Anyone can submit an application"
  on applications for insert
  to anon
  with check (true);

-- Index for admin queries
create index idx_applications_created on applications (created_at desc);
create index idx_applications_role on applications (role);
