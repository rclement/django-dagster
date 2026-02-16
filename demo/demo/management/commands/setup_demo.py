from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand

from django_dagster.models import DagsterJob, DagsterRun
from reports.models import ReportRequest


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

        # --- Viewer (staff, view-only + reports) ---
        viewer, created = User.objects.get_or_create(
            username="viewer",
            defaults={"is_staff": True},
        )
        if created:
            viewer.set_password("viewer")
            viewer.save()

        job_ct = ContentType.objects.get_for_model(DagsterJob)
        run_ct = ContentType.objects.get_for_model(DagsterRun)
        report_ct = ContentType.objects.get_for_model(ReportRequest)
        viewer.user_permissions.set([
            Permission.objects.get(content_type=job_ct, codename="view_dagsterjob"),
            Permission.objects.get(content_type=run_ct, codename="view_dagsterrun"),
            # Reports app: viewer can browse and create report requests
            Permission.objects.get(content_type=report_ct, codename="view_reportrequest"),
            Permission.objects.get(content_type=report_ct, codename="add_reportrequest"),
        ])
        if created:
            self.stdout.write(self.style.SUCCESS("Created staff user 'viewer' (password: viewer)"))
        else:
            self.stdout.write("User 'viewer' already exists, permissions updated.")

        self.stdout.write()
        self.stdout.write("Demo is ready! Start the server with:")
        self.stdout.write("  python manage.py runserver")
        self.stdout.write()
        self.stdout.write("Login credentials:")
        self.stdout.write("  admin  / admin   — full access (superuser)")
        self.stdout.write("  viewer / viewer  — view-only (cannot trigger, cancel, or re-execute)")
        self.stdout.write()
        self.stdout.write("Try the Reports app (Reports > Report requests) to see how")
        self.stdout.write("custom Django models can trigger Dagster jobs behind the scenes.")
