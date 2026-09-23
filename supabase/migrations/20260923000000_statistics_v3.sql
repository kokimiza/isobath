-- statistics.md §§1, 7, 8: completed-time extraction and private posterior snapshots.
create or replace view analysis.responses as
select p.pseudo_id, s.id as session_id, s.kind, s.phase, s.item_set_version,
       s.assignment_rule, q.purpose, q.selection_prob,
       a.question_id, a.value, a.response_ms, a.answered_at,
       f.data_quality_score, f.flags, s.completed_at
from app.answers a
join app.survey_sessions s on s.id = a.session_id
join app.survey_session_questions q on q.session_id = a.session_id and q.question_id = a.question_id
join app.profiles p on p.user_id = a.user_id
left join app.quality_flags f on f.session_id = a.session_id
where s.status = 'completed'
  and p.pseudo_id in (select pseudo_id from analysis.research_participants);

alter table app.position_snapshots
  add column uncertainty jsonb,
  add column unmatched jsonb,
  add column inference_mode text check (inference_mode in ('joint', 'cut')),
  add column draws_x real[][];

-- Narrow batch-only bridge for an active participant's private training posterior.
-- No general SELECT on profiles/identity is granted to the batch role.
create function app.batch_research_key(target uuid) returns uuid
language sql stable security definer set search_path = '' as $$
  select p.pseudo_id from app.profiles p
  where p.user_id = target
    and p.pseudo_id in (select pseudo_id from analysis.research_participants)
$$;
revoke all on function app.batch_research_key(uuid) from public, anon, authenticated;
grant execute on function app.batch_research_key(uuid) to isobath_batch;
