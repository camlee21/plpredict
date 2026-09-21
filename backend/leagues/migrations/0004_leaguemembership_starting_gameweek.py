from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_from_league(apps, schema_editor):
    """Existing memberships predate per-member start tracking, so they inherit
    their league's own starting gameweek - the closest thing to when they
    joined that was recorded at the time."""
    League = apps.get_model("leagues", "League")
    LeagueMembership = apps.get_model("leagues", "LeagueMembership")
    LeagueMembership.objects.update(
        starting_gameweek=Subquery(
            League.objects.filter(pk=OuterRef("league_id")).values("starting_gameweek")[:1]
        )
    )


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0003_league_starting_gameweek'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaguemembership',
            name='starting_gameweek',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_from_league, migrations.RunPython.noop),
    ]
