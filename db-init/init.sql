-- Auth service bootstrap SQL
-- This script keeps auth service compatible with migration runners.
-- Use full_db_dump.sql for full schema provisioning in fresh environments.

BEGIN;

-- Ensure SUPERADMIN role is present.
INSERT INTO public.roles (role_name)
SELECT 'SUPERADMIN'
WHERE NOT EXISTS (SELECT 1 FROM public.roles WHERE role_name = 'SUPERADMIN');

-- Remove legacy SUPERADMIN1 role if present.
DELETE FROM public.user_roles
WHERE role_id IN (SELECT id FROM public.roles WHERE role_name = 'SUPERADMIN1');

DELETE FROM public.roles WHERE role_name = 'SUPERADMIN1';

COMMIT;
