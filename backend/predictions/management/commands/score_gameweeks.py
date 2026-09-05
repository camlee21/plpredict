from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from backend.fixtures.models import Fixture, Gameweek
from backend.predictions.models import Prediction
from backend.predictions.scoring import calculate_points


class Command(BaseCommand):
    help = (
        "Finalises scores for any gameweek whose finalize_after time has passed: "
        "awards points to every prediction for a finished fixture. Run this "
        "periodically (e.g. every 5-10 minutes) alongside sync_fixtures."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        candidates = Gameweek.objects.filter(is_scored=False, finalize_after__isnull=False, finalize_after__lte=now)

        scored_count = 0
        for gameweek in candidates:
            matches = list(gameweek.matches.all())
            if not matches:
                continue

            scorable = [m for m in matches if m.status != Fixture.Status.POSTPONED]
            if not scorable or not all(m.is_finished for m in scorable):
                self.stdout.write(
                    self.style.WARNING(
                        f"Gameweek {gameweek.number}: not all fixtures are finished yet, skipping."
                    )
                )
                continue

            for fixture in scorable:
                predictions = Prediction.objects.filter(fixture=fixture, points__isnull=True)
                for prediction in predictions:
                    prediction.points = calculate_points(
                        prediction.predicted_home_score,
                        prediction.predicted_away_score,
                        fixture.home_score,
                        fixture.away_score,
                    )
                    prediction.save(update_fields=["points"])
                    scored_count += 1

            gameweek.is_scored = True
            gameweek.save(update_fields=["is_scored"])
            self.stdout.write(self.style.SUCCESS(f"Finalised gameweek {gameweek.number}."))

        self.stdout.write(self.style.SUCCESS(f"Scored {scored_count} predictions."))
