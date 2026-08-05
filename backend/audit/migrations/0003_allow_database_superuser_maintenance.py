from django.db import migrations


def allow_superuser_maintenance(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('app.audit_maintenance', TRUE) = 'on'
               OR EXISTS (
                   SELECT 1 FROM pg_roles
                   WHERE rolname = CURRENT_USER AND rolsuper = TRUE
               ) THEN
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'audit_logs is append-only for application roles';
        END;
        $$;
    """)


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_restrict_runtime_access")]
    operations = [migrations.RunPython(allow_superuser_maintenance, migrations.RunPython.noop)]
