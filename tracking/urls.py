from django.urls import path

from .views import MapView, TrafficDataAPIView, VehicleDataAPIView

app_name = "tracking"

urlpatterns = [
    path("", MapView.as_view(), name="map"),
    path("api/vehicles/", VehicleDataAPIView.as_view(), name="vehicle-data"),
    path("api/traffic/", TrafficDataAPIView.as_view(), name="traffic-data"),
]
