# api/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, F, Count

# Import your models from your other apps
from payment.models import OrderItem
from store.models import Product 
from .serializers import RevenuePerCategorySerializer, LeastDesirableProductSerializer

class TotalRevenuePerCategoryView(APIView):
    """
    API endpoint to get the total revenue for each product category.
    """
    def get(self, request, *args, **kwargs):
        # This query groups items by product category and calculates the total revenue.
        revenue_data = OrderItem.objects.values('product__category__name') \
            .annotate(
                product_category=F('product__category__name'),
                total_revenue=Sum(F('quantity') * F('price'))
            ).values('product_category', 'total_revenue')

        serializer = RevenuePerCategorySerializer(revenue_data, many=True)
        return Response(serializer.data)


class LeastDesirableProductView(APIView):
    """
    API endpoint to find the product sold in the least quantity.
    """
    def get(self, request, *args, **kwargs):
        # This query finds the product with the lowest total sold quantity.
        least_sold_product = OrderItem.objects.values('product__name') \
            .annotate(total_quantity=Sum('quantity')) \
            .order_by('total_quantity').first()
        
        # If there are no orders, return an empty response.
        if not least_sold_product:
            return Response({})
            
        # Rename the key to match the serializer
        least_sold_product['product_name'] = least_sold_product.pop('product__name')

        serializer = LeastDesirableProductSerializer(least_sold_product)
        return Response(serializer.data)