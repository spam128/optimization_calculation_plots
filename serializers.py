from rest_framework import serializers


class PlotDataSerializer(serializers.Serializer):
    label = serializers.CharField(required=True, max_length=100)
    data = serializers.ListField(child=serializers.DictField())
    unit = serializers.CharField(required=True, max_length=100)
