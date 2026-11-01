"""
Copy every record from an SQLite database file into the (PostgreSQL) default database, then prove the copy.

    python manage.py import_sqlite backups/db.sqlite3.pre-multitenant-2026-11-01
    python manage.py import_sqlite <file> --verify-only      # compare again, change nothing

The SQLite file is opened read-only and never changed. Both databases must be at the same migration state, and
the target must hold no leads (use --replace to empty a target that does). Primary keys are kept, sequences are
moved past the copied ids, and every table is then compared row by row: counts and every column value.
See docs/DATABASE_MIGRATION.md.
"""

from pathlib import Path

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connections, transaction
from django.db.migrations.recorder import MigrationRecorder

SOURCE = "sqlite_import"
# Rebuilt by Django on every database (content types, permissions) or not worth copying (sessions).
SKIP_MODELS = {"contenttypes.contenttype", "auth.permission", "sessions.session"}


class Command(BaseCommand):
    help = "Copy all data from an SQLite file into the default (PostgreSQL) database and verify the copy."

    def add_arguments(self, parser):
        parser.add_argument("sqlite_path")
        parser.add_argument("--verify-only", action="store_true", help="Only compare the two databases.")
        parser.add_argument("--replace", action="store_true", help="Empty a target that already holds data.")

    def handle(self, sqlite_path, verify_only=False, replace=False, **options):
        path = Path(sqlite_path).resolve()
        if not path.is_file():
            raise CommandError(f"No SQLite file at {path}")
        if connections["default"].vendor != "postgresql":
            raise CommandError("The default database is not PostgreSQL: set DB_ENGINE=postgres and the DB_* settings.")
        self._open_source(path)

        source_migrations = MigrationRecorder(connections[SOURCE]).applied_migrations().keys()
        target_migrations = MigrationRecorder(connections["default"]).applied_migrations().keys()
        if set(source_migrations) != set(target_migrations):
            missing = sorted(set(source_migrations) ^ set(target_migrations))[:10]
            raise CommandError(
                "The databases are at different migration states. Run `migrate` on the target with the code that "
                f"matches the SQLite file first. Differences: {missing}"
            )

        if not verify_only:
            self._copy(path, replace)
        problems = self._verify()
        if problems:
            for problem in problems:
                self.stderr.write(self.style.ERROR(problem))
            raise CommandError(f"Verification failed: {len(problems)} difference(s).")
        self.stdout.write(self.style.SUCCESS("Verified: every table matches the SQLite file row for row."))

    def _open_source(self, path):
        # Read-only URI: nothing can be written to the original file, not even a WAL checkpoint.
        databases = {**connections.settings, SOURCE: {"ENGINE": "django.db.backends.sqlite3", "NAME": f"file:{path.as_posix()}?mode=ro"}}
        connections.settings[SOURCE] = connections.configure_settings(databases)[SOURCE]

    def _copy(self, path, replace):
        from leads.models import Enquiry

        if Enquiry.objects.using("default").exists() and not replace:
            raise CommandError("The target database already holds leads. Use --replace to empty it first.")

        dump = path.with_name(f"{path.name}.import.json")
        self.stdout.write(f"Reading {path.name} (read-only)…")
        call_command(
            "dumpdata", database=SOURCE, natural_foreign=True, exclude=sorted(SKIP_MODELS), output=str(dump), verbosity=0
        )
        with transaction.atomic(using="default"):
            # Data migrations (starting landing-page content, the editors group) fill a fresh database; the copy
            # replaces all of it so ids match the original exactly.
            call_command("flush", database="default", interactive=False, verbosity=0)
            self.stdout.write("Writing to PostgreSQL…")
            call_command("loaddata", str(dump), database="default", verbosity=0)
            models = [m for m in apps.get_models(include_auto_created=True)]
            sql = connections["default"].ops.sequence_reset_sql(no_style(), models)
            with connections["default"].cursor() as cursor:
                for statement in sql:
                    cursor.execute(statement)
        self.stdout.write(f"Copied. The intermediate file {dump.name} holds customer data: delete it when done.")

    def _verify(self):
        problems = []
        checked = 0
        for model in apps.get_models(include_auto_created=True):
            label = model._meta.label_lower
            if label in SKIP_MODELS or not model._meta.managed:
                continue
            rows = {}
            for alias in (SOURCE, "default"):
                rows[alias] = [self._row(model, obj) for obj in model._default_manager.using(alias).order_by("pk")]
            checked += 1
            if len(rows[SOURCE]) != len(rows["default"]):
                problems.append(f"{label}: {len(rows[SOURCE])} rows in SQLite, {len(rows['default'])} in PostgreSQL")
            elif rows[SOURCE] != rows["default"]:
                diff = next(i for i, (a, b) in enumerate(zip(rows[SOURCE], rows["default"])) if a != b)
                problems.append(f"{label}: row {rows[SOURCE][diff][0]} differs")
            else:
                self.stdout.write(f"  {label}: {len(rows[SOURCE])} rows match")
        self.stdout.write(f"{checked} tables compared.")
        return problems

    @staticmethod
    def _row(model, obj):
        values = []
        for field in model._meta.concrete_fields:
            value = getattr(obj, field.attname)
            # Permission and content type ids differ between databases: compare what they point to.
            if field.is_relation and field.related_model._meta.label_lower in SKIP_MODELS:
                related = getattr(obj, field.name)
                value = related.natural_key() if related else None
            elif hasattr(value, "name") and not isinstance(value, str):  # File fields
                value = value.name
            values.append(value)
        return tuple(values)
