BEGIN;

-- Ensure SUPERADMIN role exists.
INSERT INTO public.roles (role_name)
SELECT 'SUPERADMIN'
WHERE NOT EXISTS (SELECT 1 FROM public.roles WHERE role_name = 'SUPERADMIN');

-- Migrate SUPERADMIN1 user-role assignments to SUPERADMIN.
WITH superadmin1_role AS (
    SELECT id FROM public.roles WHERE role_name = 'SUPERADMIN1' LIMIT 1
),
superadmin_role AS (
    SELECT id FROM public.roles WHERE role_name = 'SUPERADMIN' LIMIT 1
)
INSERT INTO public.user_roles (user_id, role_id)
SELECT ur.user_id, sr.id
FROM public.user_roles ur
JOIN superadmin1_role r1 ON ur.role_id = r1.id
JOIN superadmin_role sr ON TRUE
ON CONFLICT DO NOTHING;

-- Remove old SUPERADMIN1 user-role assignments.
DELETE FROM public.user_roles
WHERE role_id IN (SELECT id FROM public.roles WHERE role_name = 'SUPERADMIN1');

-- Remove SUPERADMIN1 role.
DELETE FROM public.roles
WHERE role_name = 'SUPERADMIN1';

COMMIT;
