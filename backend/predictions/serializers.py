from rest_framework import serializers

from backend.fixtures.serializers import FixtureSerializer

from .models import Prediction


class PredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prediction
        fields = ("id", "fixture", "predicted_home_score", "predicted_away_score", "points")


class FixtureWithPredictionSerializer(FixtureSerializer):
    prediction = serializers.SerializerMethodField()

    class Meta(FixtureSerializer.Meta):
        fields = FixtureSerializer.Meta.fields + ("prediction",)

    def get_prediction(self, fixture):
        prediction = self.context.get("predictions_by_fixture", {}).get(fixture.id)
        if prediction is None:
            return None
        return PredictionSerializer(prediction).data


class PredictionInputSerializer(serializers.Serializer):
    fixture_id = serializers.IntegerField()
    home_score = serializers.IntegerField(min_value=0, max_value=10)
    away_score = serializers.IntegerField(min_value=0, max_value=10)


class BulkPredictionSerializer(serializers.Serializer):
    predictions = PredictionInputSerializer(many=True)
