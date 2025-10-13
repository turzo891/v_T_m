from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.generic import TemplateView, View

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
        return context


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
