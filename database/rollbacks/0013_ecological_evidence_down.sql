-- Destructive database rollback for 0013_ecological_evidence.sql.
-- Private Storage objects and the bucket are deliberately preserved for recovery.

drop policy if exists ecological_evidence_objects_authorized_insert on storage.objects;
drop policy if exists ecological_evidence_objects_member_select on storage.objects;

drop trigger if exists ecological_evidence_set_updated_at on ecological_evidence;
drop function if exists set_ecological_evidence_updated_at();
drop table if exists ecological_evidence_history;
drop table if exists ecological_evidence_media;
drop table if exists ecological_evidence;
