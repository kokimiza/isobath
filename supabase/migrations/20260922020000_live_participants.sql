-- Participant count shown to users is live, not the nightly snapshot: the batch updates positions
-- and the chart, but a completed survey should count immediately. Aggregate only (no user rows),
-- so isobath_api gets this one function instead of a grant on survey_sessions (design §4.4).
create function app.completed_participants() returns bigint
language sql stable security definer set search_path = '' as $$
  select count(distinct user_id) from app.survey_sessions
  where kind = 'initial' and status = 'completed'
$$;
revoke all on function app.completed_participants() from public, anon, authenticated;
grant execute on function app.completed_participants() to isobath_api;
