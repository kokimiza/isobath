-- Research attributes never travel in Auth metadata. Authentication creates a
-- pending account; a JWT-bound API transaction completes registration afterwards.
create table app.research_demographics (
  user_id uuid primary key references auth.users(id) on delete cascade,
  birth_year smallint not null check (birth_year between 1 and 9999),
  birth_month smallint not null check (birth_month between 1 and 12),
  gender text not null check (gender in ('male','female','neither','prefer_not_to_say')),
  collected_at timestamptz not null default now()
);
create table app.pending_registrations (
  user_id uuid primary key references auth.users(id) on delete cascade
);
alter table app.research_demographics enable row level security;
alter table app.pending_registrations enable row level security;
revoke all on app.research_demographics, app.pending_registrations from public,
  anon, authenticated, isobath_api, isobath_batch, isobath_pipeline;

create or replace function app.on_auth_user_created() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into app.profiles(user_id) values(new.id);
  insert into app.pending_registrations(user_id) values(new.id);
  return new;
end $$;

create function app.registration_required() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists(select 1 from app.pending_registrations where user_id = auth.uid())
$$;
revoke all on function app.registration_required() from public, anon;
grant execute on function app.registration_required() to authenticated;

-- Write-only, own-account capability. The API has no SELECT on attributes.
create function app.complete_registration(birth_y integer, birth_m integer, gender_value text)
returns boolean language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'not authenticated' using errcode = '42501';
  end if;
  perform 1 from app.pending_registrations where user_id = uid for update;
  if not found then return false; end if;
  if birth_y is null or birth_m is null or gender_value is null
     or birth_y not between 1 and 9999 or birth_m not between 1 and 12
     or gender_value not in ('male','female','neither','prefer_not_to_say') then
    raise exception 'invalid research demographics' using errcode = '23514';
  end if;
  if make_date(birth_y,birth_m,1) > (now() at time zone 'Asia/Tokyo')::date then
    raise exception 'future birth month' using errcode = '23514';
  end if;
  insert into app.research_demographics(user_id,birth_year,birth_month,gender)
    values(uid,birth_y,birth_m,gender_value);
  delete from app.pending_registrations where user_id = uid;
  return true;
end $$;
revoke all on function app.complete_registration(integer,integer,text) from public, anon;
grant execute on function app.complete_registration(integer,integer,text) to authenticated;

-- Expanded research terms require a new grant, never silently upgrade old consent.
create or replace view analysis.research_participants as
select pseudo_id from (
  select distinct on (pseudo_id) pseudo_id, action, version
  from app.consent_events where document = 'research'
  order by pseudo_id, id desc
) latest where action = 'grant' and version = '2';

create view analysis.research_demographics as
select p.pseudo_id, d.birth_year, d.birth_month, d.gender
from app.research_demographics d
join app.profiles p on p.user_id = d.user_id
where p.pseudo_id in (select pseudo_id from analysis.research_participants)
  and not exists (select 1 from app.deletion_tombstones t where t.pseudo_id = p.pseudo_id);
revoke all on analysis.research_demographics from public, anon, authenticated,
  isobath_api, isobath_batch;
grant select on analysis.research_demographics to isobath_pipeline;

comment on table app.research_demographics is
  'Research-only self report. API can write own pending registration through a function, never SELECT. Not for positions, eligibility or advertising.';
