-- ISOBATH initial schema (design.md §4)
-- app      : application tables. NOT exposed via Data API (design D-1)
-- analysis : pseudonymized views for the offline pipeline

create schema if not exists app;
create schema if not exists analysis;

revoke all on schema app from public, anon, authenticated;
revoke all on schema analysis from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- Roles
-- Passwords are set out of band:  alter role isobath_api password '...';
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'isobath_api') then
    create role isobath_api login noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'isobath_pipeline') then
    create role isobath_pipeline login noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'isobath_batch') then
    create role isobath_batch login noinherit;
  end if;
end $$;

grant authenticated to isobath_api;          -- allows SET ROLE authenticated (design D-2)
grant usage on schema app to isobath_api, isobath_batch, authenticated;
grant usage on schema analysis to isobath_pipeline;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
create table app.profiles (
  user_id      uuid primary key references auth.users on delete cascade,
  pseudo_id    uuid not null unique default gen_random_uuid(),
  observer_no  bigint generated always as identity unique,
  created_at   timestamptz not null default now()
);

-- Append-only consent history (grant / withdraw). Research participation is optional and
-- can be withdrawn without deleting the account. On account deletion user_id becomes null and
-- only pseudo_id + events remain as minimal evidence (retention: data-retention policy).
create table app.consent_events (
  id         bigint generated always as identity primary key,
  user_id    uuid references app.profiles on delete set null,
  pseudo_id  uuid not null,
  document   text not null check (document in ('terms', 'privacy', 'research')),
  version    text not null,
  action     text not null check (action in ('grant', 'withdraw')),
  at         timestamptz not null default now()
);
create index on app.consent_events (user_id, document, id desc);
create index on app.consent_events (pseudo_id, document, id desc);

create table app.questions (
  id                int primary key,
  code              text not null unique,
  item_set_version  text not null,
  kind              text not null check (kind in ('personality', 'quality', 'comparison')),
  domain            text,
  facet             text,
  keyed             smallint check (keyed in (1, -1)),
  anchor            boolean not null default false,
  block_no          smallint check (block_no >= 0),
  linking           boolean not null default false,
  status            text not null check (status in ('candidate', 'formal', 'retired')),
  quality_rule      jsonb,           -- {"type":"attention","expect":4} | {"type":"repeat","of":"D01-03"}
  text_ja           text not null,
  check (not (anchor and block_no is not null)),
  check (kind = 'personality' or (not anchor and block_no is null))
);
create index on app.questions (item_set_version);

create table app.survey_sessions (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references app.profiles on delete cascade,
  kind              text not null check (kind in ('initial', 'continuous')),
  status            text not null default 'open' check (status in ('open', 'completed', 'abandoned')),
  item_set_version  text not null,
  phase             smallint not null default 1,
  assignment_rule   text not null,
  blocks            smallint[] not null default '{}',
  created_at        timestamptz not null default now(),
  completed_at      timestamptz,
  unique (id, user_id),
  check ((status = 'completed') = (completed_at is not null))
);
create unique index one_open_session on app.survey_sessions (user_id) where status = 'open';
create unique index one_initial_session on app.survey_sessions (user_id)
  where kind = 'initial' and status <> 'abandoned';

create table app.survey_session_questions (
  session_id      uuid not null,
  user_id         uuid not null,
  question_id     int  not null references app.questions,
  seq             smallint not null,
  purpose         text not null check (purpose in ('anchor', 'block', 'quality', 'retest', 'comparison')),
  selection_prob  real not null check (selection_prob > 0 and selection_prob <= 1),
  primary key (session_id, question_id),
  unique (session_id, seq),
  foreign key (session_id, user_id) references app.survey_sessions (id, user_id) on delete cascade
);

create table app.answers (
  session_id   uuid not null,
  user_id      uuid not null,
  question_id  int  not null,
  value        smallint not null check (value between 1 and 5),
  response_ms  int check (response_ms >= 0),
  answered_at  timestamptz not null default now(),
  primary key (session_id, question_id),
  -- only assigned questions can be answered (DR-04 / design D-3)
  foreign key (session_id, question_id)
    references app.survey_session_questions (session_id, question_id) on delete cascade,
  foreign key (session_id, user_id) references app.survey_sessions (id, user_id) on delete cascade
);
create index on app.answers (user_id, question_id, answered_at desc);

create table app.quality_flags (
  session_id   uuid primary key,
  user_id      uuid not null,
  flags        jsonb not null,
  data_quality_score  real not null check (data_quality_score between 0 and 1),
  computed_at  timestamptz not null default now(),
  foreign key (session_id, user_id) references app.survey_sessions (id, user_id) on delete cascade
);

create table app.position_snapshots (
  id             bigint generated always as identity primary key,
  user_id        uuid not null,
  session_id     uuid not null,             -- latest session completed before the cutoff
  cutoff_at      timestamptz not null,      -- nightly batch that produced it (requirements §4.1)
  chart_version  text not null,
  stage          text not null,
  latent         real[] not null,
  latent_se      real[] not null,
  map_xy         real[] not null,
  confidence     real not null,
  memberships    jsonb,
  near_boundary  boolean,
  created_at     timestamptz not null default now(),
  foreign key (session_id, user_id) references app.survey_sessions (id, user_id) on delete cascade
);
create index on app.position_snapshots (user_id, id desc);
create unique index on app.position_snapshots (user_id, cutoff_at);

-- Nightly batch runs (design §5.13). One row per cutoff (01:00 JST) makes reruns idempotent.
create table app.batch_runs (
  cutoff_at      timestamptz primary key,
  status         text not null check (status in ('running', 'succeeded', 'failed')),
  chart_version  text not null,
  stage          text not null,
  participants   int,
  placed         int,
  map            jsonb,          -- aggregated density grid, cells under k suppressed
  started_at     timestamptz not null default now(),
  finished_at    timestamptz,
  error          text
);
create index on app.survey_sessions (completed_at) where status = 'completed';

create table app.deletion_tombstones (
  pseudo_id   uuid primary key,
  deleted_at  timestamptz not null default now()
);

create table app.audit_events (
  id          bigint generated always as identity primary key,
  at          timestamptz not null default now(),
  actor_hash  text,
  action      text not null,
  detail      jsonb
);

-- ---------------------------------------------------------------------------
-- Grants (minimum for authenticated; RLS below narrows rows)
-- ---------------------------------------------------------------------------
revoke all on all tables in schema app from public, anon, authenticated;

grant select                    on app.profiles                 to authenticated;
grant select, insert            on app.consent_events           to authenticated;
grant select                    on app.questions                to authenticated;
grant select, insert            on app.survey_sessions          to authenticated;
grant update (status, completed_at) on app.survey_sessions      to authenticated;
grant select, insert            on app.survey_session_questions to authenticated;
grant select, insert            on app.answers                  to authenticated;
grant insert, update            on app.quality_flags            to authenticated;
grant select                    on app.position_snapshots       to authenticated;  -- written by the batch only

-- ---------------------------------------------------------------------------
-- RLS (DR-05): one policy per operation
-- ---------------------------------------------------------------------------
alter table app.profiles                 enable row level security;
alter table app.consent_events           enable row level security;
alter table app.questions                enable row level security;
alter table app.survey_sessions          enable row level security;
alter table app.survey_session_questions enable row level security;
alter table app.answers                  enable row level security;
alter table app.quality_flags            enable row level security;
alter table app.position_snapshots       enable row level security;
alter table app.deletion_tombstones      enable row level security;
alter table app.audit_events             enable row level security;
alter table app.batch_runs               enable row level security;

create policy profiles_select on app.profiles for select to authenticated
  using (user_id = (select auth.uid()));

create policy consents_select on app.consent_events for select to authenticated
  using (user_id = (select auth.uid()));
create policy consents_insert on app.consent_events for insert to authenticated
  with check (user_id = (select auth.uid()));

create policy questions_select on app.questions for select to authenticated
  using (true);

create policy sessions_select on app.survey_sessions for select to authenticated
  using (user_id = (select auth.uid()));
create policy sessions_insert on app.survey_sessions for insert to authenticated
  with check (user_id = (select auth.uid()) and status = 'open');
create policy sessions_update on app.survey_sessions for update to authenticated
  using (user_id = (select auth.uid()) and status = 'open')
  with check (user_id = (select auth.uid()));

create policy ssq_select on app.survey_session_questions for select to authenticated
  using (user_id = (select auth.uid()));
create policy ssq_insert on app.survey_session_questions for insert to authenticated
  with check (user_id = (select auth.uid()));

create policy answers_select on app.answers for select to authenticated
  using (user_id = (select auth.uid()));
create policy answers_insert on app.answers for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and exists (
      select 1 from app.survey_sessions s
      where s.id = session_id and s.status = 'open'
    )
  );

create policy quality_insert on app.quality_flags for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy quality_update on app.quality_flags for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy snapshots_select on app.position_snapshots for select to authenticated
  using (user_id = (select auth.uid()));
-- nightly batch: explicit per-table policies instead of BYPASSRLS (design §4.3)
grant select on app.survey_sessions, app.answers, app.consent_events to isobath_batch;
grant select, insert, update on app.position_snapshots, app.batch_runs to isobath_batch;
create policy batch_sessions on app.survey_sessions for select to isobath_batch using (true);
create policy batch_answers on app.answers for select to isobath_batch using (true);
create policy batch_consents on app.consent_events for select to isobath_batch using (true);
create policy batch_snapshots_select on app.position_snapshots for select to isobath_batch using (true);
create policy batch_snapshots_insert on app.position_snapshots for insert to isobath_batch with check (true);
create policy batch_snapshots_update on app.position_snapshots for update to isobath_batch using (true);
create policy batch_runs_select on app.batch_runs for select to isobath_batch, isobath_api using (true);
create policy batch_runs_insert on app.batch_runs for insert to isobath_batch with check (true);
create policy batch_runs_update on app.batch_runs for update to isobath_batch using (true);
grant select on app.batch_runs to isobath_api;  -- aggregates only: stage, counts, density grid

-- deletion_tombstones / audit_events: no policies -> only SECURITY DEFINER functions

-- ---------------------------------------------------------------------------
-- Views / functions
-- SECURITY DEFINER functions are privilege-escalation boundaries (design §4.4):
--   set search_path = '', fully qualified names only, revoke from public, grant to one role.
-- ---------------------------------------------------------------------------

create function app.fill_consent_pseudo_id() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.pseudo_id := (select p.pseudo_id from app.profiles p where p.user_id = new.user_id);
  if new.pseudo_id is null then
    raise exception 'profile not found' using errcode = '23503';
  end if;
  return new;
end $$;

create trigger fill_consent_pseudo_id
  before insert on app.consent_events
  for each row execute function app.fill_consent_pseudo_id();

-- current state per user x document (latest event wins)
create view app.consent_state with (security_invoker = true) as
select distinct on (user_id, document) user_id, document, version, action = 'grant' as granted, at
from app.consent_events
where user_id is not null
order by user_id, document, id desc;
grant select on app.consent_state to authenticated;

-- latest answer per user x question (ST-POS-04)
create view app.latest_answers with (security_invoker = true) as
select distinct on (a.user_id, a.question_id)
       a.user_id, a.question_id, a.value, a.answered_at
from app.answers a
order by a.user_id, a.question_id, a.answered_at desc;
grant select on app.latest_answers to authenticated;

create function app.on_auth_user_created() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into app.profiles (user_id) values (new.id);
  return new;
end $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function app.on_auth_user_created();
revoke all on function app.on_auth_user_created() from public, anon, authenticated;

-- account deletion without service_role (design D-6, SEC-DEL-01)
create function app.delete_me() returns void
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  pid uuid;
begin
  if uid is null then
    raise exception 'not authenticated' using errcode = '42501';
  end if;
  select pseudo_id into pid from app.profiles where user_id = uid;
  if pid is not null then
    insert into app.deletion_tombstones (pseudo_id) values (pid) on conflict do nothing;
  end if;
  insert into app.audit_events (actor_hash, action)
    values (encode(extensions.digest(uid::text, 'sha256'), 'hex'), 'account.delete');
  delete from auth.users where id = uid;   -- cascades to app.*
end $$;
revoke all on function app.delete_me() from public, anon;
grant execute on function app.delete_me() to authenticated;

-- ---------------------------------------------------------------------------
-- analysis: pseudonymized, pipeline-only (SEC-PRV-01)
-- ---------------------------------------------------------------------------
create view analysis.research_participants as
select pseudo_id from (
  select distinct on (pseudo_id) pseudo_id, action
  from app.consent_events
  where document = 'research'
  order by pseudo_id, id desc
) latest
where action = 'grant';

create view analysis.responses as
select p.pseudo_id, s.id as session_id, s.kind, s.phase, s.item_set_version,
       s.assignment_rule, q.purpose, q.selection_prob,
       a.question_id, a.value, a.response_ms, a.answered_at,
       f.data_quality_score, f.flags
from app.answers a
join app.survey_sessions s on s.id = a.session_id
join app.survey_session_questions q on q.session_id = a.session_id and q.question_id = a.question_id
join app.profiles p on p.user_id = a.user_id
left join app.quality_flags f on f.session_id = a.session_id
where s.status = 'completed'
  and p.pseudo_id in (select pseudo_id from analysis.research_participants);

create view analysis.questions as
select id, code, item_set_version, kind, domain, facet, keyed, anchor, block_no, linking, status
from app.questions;

create view analysis.tombstones as
select pseudo_id, deleted_at from app.deletion_tombstones;

revoke all on all tables in schema analysis from public, anon, authenticated;
grant select on all tables in schema analysis to isobath_pipeline;
