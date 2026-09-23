-- Minimal stand-in for the Supabase objects our migration depends on.
-- Lets the RLS tests run on plain PostgreSQL 15+ (docker postgres:16).
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
end $$;

create schema auth;
create table auth.users (id uuid primary key default gen_random_uuid(), email text,
  raw_user_meta_data jsonb not null default '{}');
create table auth.identities (id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users on delete cascade, identity_data jsonb);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid
$$;
grant usage on schema auth to anon, authenticated;

create schema extensions;
create extension pgcrypto schema extensions;
