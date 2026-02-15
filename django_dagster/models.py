from django.db import models


class DagsterJob(models.Model):
    class Meta:
        managed = False
        verbose_name = "Job"
        verbose_name_plural = "Jobs"


class DagsterRun(models.Model):
    class Meta:
        managed = False
        verbose_name = "Run"
        verbose_name_plural = "Runs"
