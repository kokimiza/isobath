-- LOCAL DEVELOPMENT ONLY (supabase db reset / start). Never applied to production.

alter role isobath_api password 'isobath-local';
alter role isobath_pipeline password 'isobath-local';

-- Dummy item bank (item_set_version 0.1): 30 anchors, 10 blocks x 20, 2 quality items.
-- Real items are authored per observation-domains.md (requirements Q-01).
insert into app.questions (id, code, item_set_version, kind, domain, keyed, anchor, status, text_ja)
select i, format('A%s', lpad(i::text, 2, '0')), '0.1', 'personality',
       format('D%s', lpad((((i - 1) % 16) + 1)::text, 2, '0')),
       case when i % 3 = 0 then -1 else 1 end, true, 'candidate',
       format('（開発用ダミー）アンカー項目 %s：普段の自分にどの程度あてはまりますか。', i)
from generate_series(1, 30) i;

insert into app.questions (id, code, item_set_version, kind, domain, keyed, block_no, status, text_ja)
select 100 + b * 20 + j, format('B%s-%s', b, lpad(j::text, 2, '0')), '0.1', 'personality',
       format('D%s', lpad((((b * 20 + j) % 16) + 1)::text, 2, '0')),
       case when j % 3 = 0 then -1 else 1 end, b, 'candidate',
       format('（開発用ダミー）ブロック%s 項目%s：普段の自分にどの程度あてはまりますか。', b, j)
from generate_series(0, 9) b, generate_series(1, 20) j;

insert into app.questions (id, code, item_set_version, kind, status, quality_rule, text_ja) values
  (900, 'QA1', '0.1', 'quality', 'candidate', '{"type":"attention","expect":4}',
   'この項目では「4」を選んでください。'),
  (901, 'QR1', '0.1', 'quality', 'candidate', '{"type":"repeat","of":"A01"}',
   '（開発用ダミー）アンカー項目 1 と同じ内容：普段の自分にどの程度あてはまりますか。');
