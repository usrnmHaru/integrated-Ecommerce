# api/serializers.py

from rest_framework import serializers

class RevenuePerCategorySerializer(serializers.Serializer):
    product_category = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)

class LeastDesirableProductSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    total_quantity = serializers.IntegerField()