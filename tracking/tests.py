from django.test import Client, TestCase

from . import services


class TrackingServicesTests(TestCase):
    def setUp(self):
        services.FILTER_STATE.clear()

    def test_snapshot_includes_overlays_and_identifiers(self):
        snapshot = services.get_tracking_snapshot()

        self.assertIn("geofences", snapshot)
        self.assertGreater(len(snapshot["geofences"]), 0)
        self.assertIn("depots", snapshot)
        self.assertGreater(len(snapshot["depots"]), 0)
        self.assertIn("legend", snapshot)
        self.assertIn("routes", snapshot["legend"])
        self.assertTrue(
            any(entry.get("color") for entry in snapshot["legend"]["routes"])
        )
        self.assertIn("points", snapshot["geofences"][0])
        self.assertGreater(len(snapshot["geofences"][0]["points"]), 0)

        vehicles = snapshot["vehicles"]
        self.assertGreater(len(vehicles), 0)
        unique_uids = {vehicle["uid"] for vehicle in vehicles}
        self.assertEqual(len(unique_uids), len(vehicles))

        sample = vehicles[0]
        self.assertIn("identifiers", sample)
        for key in ("license_plate", "device_id", "driver"):
            self.assertIn(key, sample["identifiers"])

        raw_point = sample["raw_location"]
        filtered_point = sample["location"]
        self.assertAlmostEqual(
            raw_point["lat"],
            filtered_point["lat"],
            delta=0.002,
        )
        self.assertAlmostEqual(
            raw_point["lng"],
            filtered_point["lng"],
            delta=0.002,
        )

    def test_filter_state_persists_between_generations(self):
        first_batch = services.generate_vehicle_data()
        second_batch = services.generate_vehicle_data()

        self.assertEqual(len(first_batch), len(second_batch))
        self.assertGreaterEqual(len(services.FILTER_STATE), len(first_batch))

        first_vehicle = second_batch[0]
        raw_point = first_vehicle["raw_location"]
        filtered_point = first_vehicle["location"]
        self.assertAlmostEqual(
            raw_point["lat"],
            filtered_point["lat"],
            delta=0.002,
        )
        self.assertAlmostEqual(
            raw_point["lng"],
            filtered_point["lng"],
            delta=0.002,
        )


class VehicleAPITests(TestCase):
    def setUp(self):
        services.FILTER_STATE.clear()
        self.client = Client()

    def test_vehicle_api_returns_enriched_payload(self):
        response = self.client.get("/api/vehicles/")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("vehicles", payload)
        self.assertIn("timestamp", payload)
        self.assertIsInstance(payload["vehicles"], list)
        if not payload["vehicles"]:
            self.fail("Vehicle API returned an empty vehicle list.")

        vehicle = payload["vehicles"][0]
        self.assertIn("uid", vehicle)
        self.assertIn("identifiers", vehicle)
        self.assertIn("route", vehicle)
        self.assertIn("trail", vehicle)
        self.assertIn("upcoming", vehicle)
        self.assertIn("raw_location", vehicle)
        self.assertIn("location", vehicle)
