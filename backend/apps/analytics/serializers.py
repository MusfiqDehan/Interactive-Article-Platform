"""Response shapes for the analytics endpoints.

These exist mainly so the endpoints appear in the OpenAPI document at all --
drf-spectacular silently *drops* a path whose response it cannot infer, so an
endpoint without one is invisible to the generated TypeScript client.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import EVENT_CHOICES


class EventSerializer(serializers.Serializer):
    name = serializers.ChoiceField(choices=EVENT_CHOICES)
    article_id = serializers.IntegerField(required=False, allow_null=True)
    target_id = serializers.CharField(required=False, allow_blank=True)
    path = serializers.CharField(required=False, allow_blank=True)
    referrer = serializers.CharField(required=False, allow_blank=True)
    locale = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.DictField(required=False)


class EventBatchSerializer(serializers.Serializer):
    events = EventSerializer(many=True)


class EventIngestResultSerializer(serializers.Serializer):
    accepted = serializers.IntegerField()
    received = serializers.IntegerField()


class TotalsSerializer(serializers.Serializer):
    views = serializers.IntegerField()
    unique_sessions = serializers.IntegerField()
    reads_completed = serializers.IntegerField()
    annotation_opens = serializers.IntegerField()
    hotspot_opens = serializers.IntegerField()
    media_plays = serializers.IntegerField()
    outbound_clicks = serializers.IntegerField()
    shares = serializers.IntegerField()


class SeriesPointSerializer(serializers.Serializer):
    day = serializers.DateField()
    views = serializers.IntegerField()
    annotation_opens = serializers.IntegerField()
    reads_completed = serializers.IntegerField()


class TopArticleSerializer(serializers.Serializer):
    article_id = serializers.IntegerField()
    title = serializers.CharField()
    slug = serializers.CharField()
    views = serializers.IntegerField()
    annotation_opens = serializers.IntegerField()
    interaction_rate = serializers.FloatField()


class TopAnnotationSerializer(serializers.Serializer):
    target_id = serializers.CharField()
    opens = serializers.IntegerField()


class SiteAnalyticsSerializer(serializers.Serializer):
    days = serializers.IntegerField()
    totals = TotalsSerializer()
    #: annotation_opens / views. The metric that says whether the interactive
    #: format is being used rather than merely served.
    interaction_rate = serializers.FloatField()
    completion_rate = serializers.FloatField()
    series = SeriesPointSerializer(many=True)
    top_articles = TopArticleSerializer(many=True)


class ArticleRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    slug = serializers.CharField()


class ArticleAnalyticsSerializer(serializers.Serializer):
    article = ArticleRefSerializer()
    days = serializers.IntegerField()
    totals = TotalsSerializer()
    interaction_rate = serializers.FloatField()
    series = SeriesPointSerializer(many=True)
    top_annotations = TopAnnotationSerializer(many=True)
