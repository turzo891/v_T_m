from __future__ import annotations

import json

from django.conf import settings
from django.http import JsonResponse
from django.views.generic import TemplateView, View, CreateView, ListView, UpdateView, DeleteView
from django.shortcuts import redirect
from django.urls import reverse_lazy


from .models import Vehicle
from .forms import VehicleForm


from .services import get_tracking_snapshot
from .traffic import get_traffic_snapshot


class MapView(TemplateView):
    template_name = "tracking/map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = get_tracking_snapshot()
        context.update(snapshot)
        # Pre-serialize payloads for browsers that lack the json_script tag.
        context["vehicles_json"] = json.dumps(snapshot["vehicles"])
        context["center_json"] = json.dumps(snapshot["center_location"])
        context["generation_time_json"] = json.dumps(snapshot["generation_time"])
        context["geofences_json"] = json.dumps(snapshot["geofences"])
        context["depots_json"] = json.dumps(snapshot["depots"])
        context["route_catalog_json"] = json.dumps(snapshot["route_catalog"])
        context["legend_json"] = json.dumps(snapshot["legend"])
        traffic_snapshot = get_traffic_snapshot()
        context["traffic_source"] = traffic_snapshot["source"]
        context["traffic_generated"] = traffic_snapshot["generated"]
        context["traffic_features_json"] = json.dumps(traffic_snapshot["features"])
        context["traffic_meta_json"] = json.dumps(
            {
                "source": traffic_snapshot["source"],
                "generated": traffic_snapshot["generated"],
            }
        )
        mapbox_token = getattr(settings, "MAPBOX_ACCESS_TOKEN", "") or ""
        mapbox_style = getattr(settings, "MAPBOX_STYLE_ID", "mapbox/streets-v12")
        openstreet_url = getattr(
            settings,
            "OPENSTREET_TILE_URL",
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        )
        openstreet_attribution = getattr(
            settings,
            "OPENSTREET_ATTRIBUTION",
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        )

        tile_providers = {}
        tile_provider_choices = []

        if mapbox_token:
            tile_providers["mapbox"] = {
                "accessToken": mapbox_token,
                "styleId": mapbox_style,
            }
            tile_provider_choices.append(
                {"key": "mapbox", "label": "Mapbox"}
            )

        tile_providers["openstreet"] = {
            "tileUrl": openstreet_url,
            "attribution": openstreet_attribution,
            "maxZoom": 19,
        }
        tile_provider_choices.append(
            {"key": "openstreet", "label": "OpenStreetMap"}
        )

        default_provider = "mapbox" if mapbox_token else "openstreet"
        context["tile_provider_choices"] = tile_provider_choices
        context["default_tile_provider"] = default_provider
        context["map_tiles_config_json"] = json.dumps(
            {
                "providers": tile_providers,
                "defaultProvider": default_provider,
            }
        )
        return context


class VehicleListView(ListView):
    model = Vehicle
    template_name = 'tracking/vehicle_list.html'

class VehicleCreateView(CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'tracking/add_vehicle.html'
    success_url = reverse_lazy('tracking:vehicle-list')

class VehicleUpdateView(UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'tracking/add_vehicle.html'
    success_url = reverse_lazy('tracking:vehicle-list')

class VehicleDeleteView(DeleteView):
    model = Vehicle
    success_url = reverse_lazy('tracking:vehicle-list')

class VehicleDisableView(View):
    def post(self, request, *args, **kwargs):
        vehicle = Vehicle.objects.get(pk=self.kwargs['pk'])
        vehicle.is_disabled = not vehicle.is_disabled
        vehicle.save()
        return redirect('tracking:vehicle-list')

import requests
from .services import haversine_km

import logging

logger = logging.getLogger(__name__)

class FindRouteView(View):
    def get(self, request, *args, **kwargs):
        start_lat = float(request.GET.get('start_lat'))
        start_lng = float(request.GET.get('start_lng'))
        end_lat = float(request.GET.get('end_lat'))
        end_lng = float(request.GET.get('end_lng'))

        logger.info(f"Finding route from ({start_lat}, {start_lng}) to ({end_lat}, {end_lng}) using OSRM")

        # OSRM API URL
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}?overview=full&geometries=geojson"

        try:
            response = requests.get(osrm_url)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()

            if data.get('code') == 'Ok' and data.get('routes'):
                route = data['routes'][0]
                # Extract coordinates and flip them for Leaflet ([lat, lon])
                route_coords = route['geometry']['coordinates']
                path = [[coord[1], coord[0]] for coord in route_coords]

                # Extract distance in meters, convert to km, and round it
                distance_km = round(route['distance'] / 1000, 2)

                logger.info(f"Successfully found route with {len(path)} points and distance {distance_km} km.")
                return JsonResponse({'path': path, 'distance': distance_km})
            else:
                logger.error(f"OSRM API could not find a route. Response: {data}")
                return JsonResponse({'path': [], 'error': 'Route not found'}, status=404)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling OSRM API: {e}")
            return JsonResponse({'path': [], 'error': 'Error contacting routing service'}, status=500)


from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

class IdleVehicleListView(View):
    def get(self, request, *args, **kwargs):
        idle_vehicles = Vehicle.objects.filter(status='idle', is_disabled=False).values('id', 'name')
        return JsonResponse(list(idle_vehicles), safe=False)

@method_decorator(csrf_exempt, name='dispatch')
class AssignVehicleView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            vehicle_id = data.get('vehicle_id')
            lat = data.get('lat')
            lng = data.get('lng')

            if not all([vehicle_id, lat, lng]):
                return JsonResponse({'error': 'Missing data'}, status=400)

            vehicle = Vehicle.objects.get(pk=vehicle_id)
            vehicle.latitude = lat
            vehicle.longitude = lng
            vehicle.status = 'en_route'
            vehicle.save()

            return JsonResponse({'success': True, 'message': f'Vehicle {vehicle.name} assigned.'})
        except Vehicle.DoesNotExist:
            return JsonResponse({'error': 'Vehicle not found'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error assigning vehicle: {e}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


class VehicleDataAPIView(View):
    def get(self, request, *args, **kwargs):
        snapshot = get_tracking_snapshot()
        return JsonResponse(
            {
                "timestamp": snapshot["generation_time"],
                "vehicles": snapshot["vehicles"],
            }
        )


class TrafficDataAPIView(View):
    def get(self, request, *args, **kwargs):
        snapshot = get_traffic_snapshot()
        return JsonResponse(
            {
                "generated": snapshot["generated"],
                "source": snapshot["source"],
                "features": snapshot["features"],
            }
        )
