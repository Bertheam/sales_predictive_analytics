from django.db import migrations


def restrict_analytics_runtime(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_roles
                WHERE rolname = 'sales_predictive_tenant_runtime'
            ) THEN
                REVOKE ALL PRIVILEGES ON TABLE audit_logs
                FROM sales_predictive_tenant_runtime;
            END IF;
        END
        $$;
    """)


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunPython(restrict_analytics_runtime, migrations.RunPython.noop)]
