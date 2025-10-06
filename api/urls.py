# api/urls.py

from django.urls import path
from .views import TotalRevenuePerCategoryView, LeastDesirableProductView

urlpatterns = [
    # This will create the URL: /ecom/totalrevenue/
    path('totalrevenue/', TotalRevenuePerCategoryView.as_view(), name='total-revenue'),
    
    # This will create the URL: /ecom/leastdesirable/
    path('leastdesirable/', LeastDesirableProductView.as_view(), name='least-desirable'),
]