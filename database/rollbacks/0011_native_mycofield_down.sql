-- Destructive rollback for 0011_native_mycofield.sql.
-- Stored evidence objects are deliberately preserved for manual recovery.

drop trigger if exists mycofield_set_updated_at on mycofield_observations;
drop function if exists set_mycofield_updated_at();
drop table if exists mycofield_observations;
