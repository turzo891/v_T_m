from django.urls import path
from .views import (
    MapView, TrafficDataAPIView, VehicleDataAPIView, VehicleListView, 
    VehicleCreateView, VehicleUpdateView, VehicleDeleteView, VehicleDisableView, 
    FindRouteView, IdleVehicleListView, AssignVehicleView
)

app_name = "tracking"

urlpatterns = [
    path("", MapView.as_view(), name="map"),
    path("vehicles/", VehicleListView.as_view(), name="vehicle-list"),
    path("vehicles/add/", VehicleCreateView.as_view(), name="add-vehicle"),
    path("vehicles/<int:pk>/edit/", VehicleUpdateView.as_view(), name="edit-vehicle"),
    path("vehicles/<int:pk>/delete/", VehicleDeleteView.as_view(), name="delete-vehicle"),
    path("vehicles/<int:pk>/disable/", VehicleDisableView.as_view(), name="disable-vehicle"),
    path("find-route/", FindRouteView.as_view(), name="find-route"),
    path("api/vehicles/", VehicleDataAPIView.as_view(), name="vehicle-data"),
    path("api/traffic/", TrafficDataAPIView.as_view(), name="traffic-data"),
    path("api/idle-vehicles/", IdleVehicleListView.as_view(), name="idle-vehicles"),
    path("api/assign-vehicle/", AssignVehicleView.as_view(), name="assign-vehicle"),
]
