import io
import textwrap
from pathlib import Path

from migrations.test_base import MigrationTestBase

from django.core.exceptions import FieldError
from django.core.management import call_command
from django.test import TransactionTestCase
from django.test.utils import override_settings


class AutodetectorUnmanagedModelTest(MigrationTestBase, TransactionTestCase):
    """Regression test for bug in autodetector with FK to managed=False model."""

    # TODO: it should also test
    #       1) [x] create new "managed=False" model with FK
    #       2) [x] add new field FK for already migrated(created) "managed=False" model
    #       3) [ ] drop field FK for already migrated(created) "managed=False" model
    #
    #       Consider also other cases to test, but currently when
    #       the solution is not known, better to let it as it is ...

    @override_settings(
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        INSTALLED_APPS=["migrations.migrations_test_apps.unmanaged_models"],
    )
    def test_create_model_migrate_crashes_on_missing_fk(self):
        out = io.StringIO()
        with self.temporary_migration_module("unmanaged_models") as tmp_dir:
            call_command("makemigrations", "unmanaged_models")
            call_command("migrate", "unmanaged_models")
            with open(Path(tmp_dir) / "0002_custom.py", "w") as custom_migration_file:
                custom_migration_content = textwrap.dedent(
                    """
                from django.db import migrations


                def forwards_func(apps, schema_editor):
                    klass_Boo = apps.get_model("unmanaged_models", "Boo")
                    klass_Boo.objects.filter(foo=1)


                class Migration(migrations.Migration):

                    dependencies = [
                        ('unmanaged_models', '0001_initial'),
                    ]

                    operations = [
                        migrations.RunPython(
                            forwards_func,
                            reverse_code=migrations.RunPython.noop
                        ),
                    ]
                """
                )
                custom_migration_file.write(custom_migration_content)
            try:
                call_command("migrate", "unmanaged_models", stdout=out)
            except FieldError:
                # this is the bug from #29177, it can not find FK in managed=False model
                pass
            self.assertIn("OK", out.getvalue())

    @override_settings(
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        INSTALLED_APPS=["migrations.migrations_test_apps.unmanaged_models_2"],
    )
    def test_add_field_migrate_crashes_on_missing_fk(self):
        out = io.StringIO()
        initial_migration_content = textwrap.dedent(
            """
            from django.db import migrations, models


            class Migration(migrations.Migration):

                initial = True

                dependencies = [
                ]

                operations = [
                    migrations.CreateModel(
                        name='Foo',
                        fields=[
                            (
                                'id',
                                models.AutoField(
                                    auto_created=True,
                                    primary_key=True,
                                    serialize=False,
                                    verbose_name='ID'
                                )
                            ),
                        ],
                        options={
                            'managed': True,
                        },
                    ),
                    migrations.CreateModel(
                        name='Boo',
                        fields=[
                            (
                                'id',
                                models.AutoField(
                                    auto_created=True,
                                    primary_key=True,
                                    serialize=False,
                                    verbose_name='ID'
                                )
                            ),
                        ],
                        options={
                            'managed': False,
                        },
                    ),
                ]
            """
        )
        with self.temporary_migration_module("unmanaged_models_2") as tmp_dir:
            with open(Path(tmp_dir) / "0001_initial.py", "w") as initial_migration_file:
                initial_migration_file.write(initial_migration_content)
            call_command("migrate", "unmanaged_models_2")
            call_command(
                "makemigrations",
                "unmanaged_models_2",
                dry_run=True,
                verbosity=3,
                stdout=out,
            )
        # explanation: currently as a side effect of a bug in #29177,
        #              there is: "No changes detected in app..."
        self.assertIn("'foo', models.ForeignKey", out.getvalue())
