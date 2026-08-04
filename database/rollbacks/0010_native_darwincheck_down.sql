-- Non-destructive DarwinCheck rollback.
-- Keep scientific trace data and remove only client policies when disabling UI.

drop policy if exists darwincheck_runs_authorized_insert on darwincheck_runs;
drop policy if exists darwincheck_runs_member_select on darwincheck_runs;
