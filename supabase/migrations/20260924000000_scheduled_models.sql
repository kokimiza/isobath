-- Reuse the batch role's existing table privileges; no new role or grant to the batch.
-- Private bundles include joint posteriors. They must never be readable by the API.
alter table app.batch_runs
  add column model_bundle bytea,
  add column refit_attempt_at timestamptz;

revoke select on app.batch_runs from isobath_api;
grant select (cutoff_at, status, chart_version, stage, participants, placed, map,
              started_at, finished_at, error) on app.batch_runs to isobath_api;

comment on column app.batch_runs.model_bundle is
  'Private numeric model and training handoff; never expose via API or CI artifacts.';
