# Generated by Django 5.0.7 on 2024-11-06 21:01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaign', '0006_thematicarea_last_modified'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='place',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='campaign.place'),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('national', 'National User'), ('regional', 'Regional User'), ('place', 'Place User')], max_length=10),
        ),
    ]
