from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand

from django_dagster.models import DagsterJob, DagsterRun


class Command(BaseCommand):
    help = "Set up the demo database with pre-configured users."

    def handle(self, *args, **options):
        call_command("migrate", verbosity=0)
        self.stdout.write("Migrations applied.")

        # --- Admin (superuser, full access) ---
        if User.objects.filter(username="admin").exists():
            self.stdout.write("User 'admin' already exists, skipping.")
        else:
            User.objects.create_superuser(
                username="admin",
                password="admin",
                email="admin@example.com",
            )
            self.stdout.write(self.style.SUCCESS("Created superuser 'admin' (password: admin)"))

        # --- Viewer (staff, view-only) ---
        if User.objects.filter(username="viewer").exists():
            self.stdout.write("User 'viewer' already exists, skipping.")
        else:
            viewer = User.objects.create_user(
                username="viewer",
                password="viewer",
                is_staff=True,
            )
            job_ct = ContentType.objects.get_for_model(DagsterJob)
            run_ct = ContentType.objects.get_for_model(DagsterRun)
            viewer.user_permissions.add(
                Permission.objects.get(content_type=job_ct, codename="view_dagsterjob"),
                Permission.objects.get(content_type=run_ct, codename="view_dagsterrun"),
            )
            self.stdout.write(self.style.SUCCESS("Created staff user 'viewer' (password: viewer) — view-only"))

        self.stdout.write()
        self.stdout.write("Demo is ready! Start the server with:")
        self.stdout.write("  python manage.py runserver")
        self.stdout.write()
        self.stdout.write("Login credentials:")
        self.stdout.write("  admin  / admin   — full access (superuser)")
        self.stdout.write("  viewer / viewer  — view-only (cannot trigger, cancel, or re-execute)")
