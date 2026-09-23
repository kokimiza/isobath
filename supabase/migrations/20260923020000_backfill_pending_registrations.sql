-- The trigger in 20260923010000 marks only accounts created after it as pending.
-- Earlier accounts (and any created before it reached this database) were never asked
-- for birth month and gender; ask them on their next consent screen.
insert into app.pending_registrations (user_id)
select p.user_id from app.profiles p
where not exists (select 1 from app.research_demographics d where d.user_id = p.user_id)
on conflict do nothing;
