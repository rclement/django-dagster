from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_dagster", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DagsterRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "managed": False,
                "verbose_name": "Run",
                "verbose_name_plural": "Runs",
            },
        ),
    ]
