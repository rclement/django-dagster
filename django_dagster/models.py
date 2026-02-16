from django.db import models


class DagsterJob(models.Model):
    class Meta:
        managed = False
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        permissions = [
            ("trigger_dagsterjob", "Can trigger Dagster jobs"),
        ]


class DagsterRun(models.Model):
    class Meta:
        managed = False
        verbose_name = "Run"
        verbose_name_plural = "Runs"
        permissions = [
            ("cancel_dagsterrun", "Can cancel Dagster runs"),
            ("reexecute_dagsterrun", "Can re-execute Dagster runs"),
        ]
