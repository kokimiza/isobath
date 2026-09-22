-- The auth.users INSERT trigger only provisions new accounts. Users registered
-- before the app schema was installed have no profile, so consent INSERTs fail
-- with "profile not found". Repair those accounts without replacing identities
-- or creating consent on their behalf. New signups continue to use the trigger.
insert into app.profiles (user_id)
select u.id from auth.users u
where not exists (select 1 from app.profiles p where p.user_id = u.id)
on conflict (user_id) do nothing;
