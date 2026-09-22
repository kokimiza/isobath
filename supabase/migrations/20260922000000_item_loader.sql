-- Item bank loader (FR-OPS-01): isobath_batch loads app/items/*.csv via `python -m isobath.items`.
-- No delete: an item is removed by status = 'retired'; answers keep referring to it.
grant select, insert, update on app.questions to isobath_batch;
create policy batch_questions_select on app.questions for select to isobath_batch using (true);
create policy batch_questions_insert on app.questions for insert to isobath_batch with check (true);
create policy batch_questions_update on app.questions for update to isobath_batch using (true);
