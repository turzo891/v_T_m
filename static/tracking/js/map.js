(function () {
    "use strict";

    const mapContainer = document.getElementById("map");
    if (!mapContainer || typeof window.L === "undefined") {
        return;
    }

    function parseJSONContent(id) {
        const el = document.getElementById(id);
        if (!el) {
            return null;
        }

        try {
            return JSON.parse(el.textContent);
        } catch (error) {
            console.error("Failed to parse JSON payload", error);
            return null;
        }
    }

    const center = parseJSONContent("initial-map-center") || { lat: 0, lng: 0 };
    const initialVehicles = parseJSONContent("initial-vehicle-data") || [];
    const initialTimestamp =
        parseJSONContent("initial-generation-time") || new Date().toISOString();
    const initialTrafficFeatures =
        parseJSONContent("initial-traffic-overlay") || [];
    const initialTrafficMeta = parseJSONContent("initial-traffic-meta") || {};
    const initialGeofences = parseJSONContent("initial-geofences") || [];
    const initialDepots = parseJSONContent("initial-depots") || [];
    const routeCatalog = parseJSONContent("initial-route-catalog") || [];
    const initialLegend = parseJSONContent("initial-map-legend") || {};
    const legendData =
        initialLegend && Object.keys(initialLegend).length
            ? initialLegend
            : {
                  routes: routeCatalog.map((route) => {
                      const distance =
                          typeof route.distance_km === "number"
                              ? `${route.distance_km.toFixed(1)} km`
                              : null;
                      return {
                          name: distance
                              ? `${route.name} (${distance})`
                              : route.name,
                          color: route.color,
                      };
                  }),
                  traffic: [
                      { label: "Heavy", color: "#ef4444" },
                      { label: "Moderate", color: "#f59e0b" },
                      { label: "Light", color: "#22c55e" },
                  ],
                  geofences: initialGeofences.map((fence) => ({
                      name: fence.name,
                      color: fence.color,
                      })),
              };
    const mapTilesConfig = parseJSONContent("map-tiles-config") || {};
    const tileProviders = mapTilesConfig.providers || {};
    const availableProviders = Object.keys(tileProviders);
    if (!availableProviders.length) {
        const warning = document.createElement("div");
        warning.className = "map-error";
        warning.textContent =
            "Map tiles unavailable. Configure at least one tile provider.";
        mapContainer.appendChild(warning);
        return;
    }

    const mapZoom = typeof center.zoom === "number" ? center.zoom : 12;
    const map = L.map(mapContainer).setView([center.lat, center.lng], mapZoom);

    let activeTileLayer = null;
    let activeProviderKey = null;

    function setMapError(message) {
        let existing = mapContainer.querySelector(".map-error");
        if (!message) {
            if (existing) {
                existing.remove();
            }
            return;
        }
        if (!existing) {
            existing = document.createElement("div");
            existing.className = "map-error";
            mapContainer.appendChild(existing);
        }
        existing.textContent = message;
    }

    function createMapboxLayer(config) {
        const token =
            typeof config.accessToken === "string"
                ? config.accessToken.trim()
                : "";
        if (!token) {
            return null;
        }
        const styleId =
            typeof config.styleId === "string" && config.styleId.trim()
                ? config.styleId.trim()
                : "mapbox/streets-v12";
        const tileUrl = `https://api.mapbox.com/styles/v1/${styleId}/tiles/{z}/{x}/{y}?access_token=${token}`;
        return L.tileLayer(tileUrl, {
            attribution:
                '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a>',
            tileSize: 512,
            zoomOffset: -1,
            maxZoom: 20,
        });
    }

    function createOpenStreetLayer(config) {
        const tileUrl =
            typeof config.tileUrl === "string" && config.tileUrl.trim()
                ? config.tileUrl.trim()
                : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
        const attribution =
            typeof config.attribution === "string" &&
            config.attribution.trim()
                ? config.attribution.trim()
                : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
        const options = {
            attribution,
        };
        if (typeof config.maxZoom === "number") {
            options.maxZoom = config.maxZoom;
        }
        return L.tileLayer(tileUrl, options);
    }

    function buildTileLayer(providerKey) {
        const config = tileProviders[providerKey];
        if (!config) {
            return null;
        }
        if (providerKey === "mapbox") {
            return createMapboxLayer(config);
        }
        if (providerKey === "openstreet") {
            return createOpenStreetLayer(config);
        }
        if (config.tileUrl) {
            return createOpenStreetLayer(config);
        }
        return null;
    }

    function activateTileProvider(providerKey) {
        const tileLayer = buildTileLayer(providerKey);
        if (!tileLayer) {
            setMapError(
                providerKey === "mapbox"
                    ? "Map tiles unavailable. Provide a Mapbox access token to render the map."
                    : "Map tiles unavailable for the selected provider."
            );
            return false;
        }

        if (activeTileLayer) {
            map.removeLayer(activeTileLayer);
        }
        tileLayer.addTo(map);
        activeTileLayer = tileLayer;
        activeProviderKey = providerKey;
        setMapError(null);
        return true;
    }

    const storedPreference =
        typeof window.localStorage !== "undefined"
            ? window.localStorage.getItem("vtms:tile-provider")
            : null;
    let preferredProvider = storedPreference && tileProviders[storedPreference]
        ? storedPreference
        : mapTilesConfig.defaultProvider;
    if (!preferredProvider || !tileProviders[preferredProvider]) {
        preferredProvider = availableProviders[0];
    }

    activateTileProvider(preferredProvider);

    const providerSelect = document.getElementById("tile-provider-select");
    if (providerSelect) {
        providerSelect.addEventListener("change", (event) => {
            if (!(event.target instanceof HTMLSelectElement)) {
                return;
            }
            const nextProvider = event.target.value;
            if (!nextProvider || nextProvider === activeProviderKey) {
                return;
            }
            const success = activateTileProvider(nextProvider);
            if (success && typeof window.localStorage !== "undefined") {
                window.localStorage.setItem("vtms:tile-provider", nextProvider);
            } else if (!success && activeProviderKey) {
                providerSelect.value = activeProviderKey;
            }
        });
        if (providerSelect.value !== preferredProvider) {
            providerSelect.value = preferredProvider;
        }
    }
    const vehicleCluster = L.markerClusterGroup({
        showCoverageOnHover: false,
        spiderfyOnMaxZoom: true,
        maxClusterRadius: 60,
    });
    map.addLayer(vehicleCluster);

    const trafficLayer = L.layerGroup();
    const geofenceLayer = L.layerGroup();
    const depotLayer = L.layerGroup();
    map.addLayer(geofenceLayer);
    map.addLayer(depotLayer);
    map.addLayer(trafficLayer);

    const trackedLayers = new Map();
    let latestVehicles = initialVehicles;
    let hasFitBounds = false;

    const filterState = {
        status: "",
        fleet_area: "",
    };

    const palette = ["#2563eb", "#0f766e", "#9333ea", "#dc2626", "#d97706"];
    const trafficPalette = {
        LIGHT: "#22c55e",
        MODERATE: "#f59e0b",
        HEAVY: "#ef4444",
        UNKNOWN: "#6366f1",
    };
    const overlayState = {
        geofences: true,
        depots: true,
        traffic: true,
    };
    let searchTerm = "";
    let selectedVehicleId = null;
    let lastFilteredVehicles = [];
    let lastHighlightedIds = new Set();

    const searchInput = document.getElementById("vehicle-search-input");
    const detailCard = document.getElementById("vehicle-detail-card");
    const detailEmpty = document.getElementById("vehicle-detail-empty");
    const detailContent = document.getElementById("vehicle-detail-content");
    const detailDriverName = document.getElementById("detail-driver-name");
    const detailDriverPhone = document.getElementById("detail-driver-phone");
    const detailDriverLicense = document.getElementById("detail-driver-license");
    const detailRouteName = document.getElementById("detail-route-name");
    const detailRouteHistory = document.getElementById("detail-route-history");
    if (searchInput) {
        searchTerm = searchInput.value || "";
    }

    function resolveColor(key) {
        if (!key) {
            return palette[0];
        }
        let hash = 0;
        for (let i = 0; i < key.length; i += 1) {
            hash = key.charCodeAt(i) + ((hash << 5) - hash);
        }
        const index = Math.abs(hash) % palette.length;
        return palette[index];
    }

    function resolveTrafficColor(severity) {
        const key = (severity || "UNKNOWN").toUpperCase();
        return trafficPalette[key] || trafficPalette.UNKNOWN;
    }

    function toLatLngs(points) {
        if (!Array.isArray(points)) {
            return [];
        }
        return points
            .map((point) => {
                if (!point) {
                    return null;
                }
                if (Array.isArray(point) && point.length >= 2) {
                    return [point[0], point[1]];
                }
                if (
                    typeof point.lat === "number" &&
                    typeof point.lng === "number"
                ) {
                    return [point.lat, point.lng];
                }
                return null;
            })
            .filter(Boolean);
    }

    function findVehicleById(vehicleId) {
        if (!Array.isArray(latestVehicles)) {
            return null;
        }
        return latestVehicles.find((vehicle) => vehicle.id === vehicleId) || null;
    }

    function formatCoordinate(point) {
        if (!point || typeof point.lat !== "number" || typeof point.lng !== "number") {
            return null;
        }
        const lat = point.lat.toFixed(5);
        const lng = point.lng.toFixed(5);
        return `${lat}, ${lng}`;
    }

    function renderVehicleDetails(vehicle) {
        if (!detailCard || !detailEmpty || !detailContent) {
            return;
        }

        if (!vehicle) {
            detailCard.classList.remove("is-active");
            detailContent.hidden = true;
            detailEmpty.hidden = false;
            if (detailRouteHistory) {
                detailRouteHistory.innerHTML =
                    '<li class="route-history-empty">No route history available.</li>';
            }
            return;
        }

        const identifiers = vehicle.identifiers || {};
        const driverName = identifiers.driver || "—";
        const driverPhone = identifiers.driver_phone || "—";
        const driverLicense = identifiers.driver_license || "—";
        const routeName = vehicle.route?.name || vehicle.fleet_area || "—";

        detailCard.classList.add("is-active");
        detailEmpty.hidden = true;
        detailContent.hidden = false;

        if (detailDriverName) {
            detailDriverName.textContent = driverName;
        }
        if (detailDriverPhone) {
            detailDriverPhone.textContent = driverPhone;
        }
        if (detailDriverLicense) {
            detailDriverLicense.textContent = driverLicense;
        }
        if (detailRouteName) {
            detailRouteName.textContent = routeName;
        }
        if (detailRouteHistory) {
            const trail = Array.isArray(vehicle.trail) ? vehicle.trail.slice(-5).reverse() : [];
            if (!trail.length) {
                detailRouteHistory.innerHTML =
                    '<li class="route-history-empty">No route history available.</li>';
            } else {
                const items = trail
                    .map((point, index) => {
                        const label = formatCoordinate(point);
                        if (!label) {
                            return null;
                        }
                        return `<li><span class="route-history-step">${index + 1}.</span> ${label}</li>`;
                    })
                    .filter(Boolean)
                    .join("");
                detailRouteHistory.innerHTML = items || '<li class="route-history-empty">No route history available.</li>';
            }
        }
    }

    function selectVehicle(vehicleId) {
        const normalizedId = Number(vehicleId);
        if (!Number.isFinite(normalizedId)) {
            selectedVehicleId = null;
            renderVehicleDetails(null);
            return;
        }
        const vehicle = findVehicleById(normalizedId);
        if (!vehicle) {
            selectedVehicleId = null;
            renderVehicleDetails(null);
            return;
        }
        selectedVehicleId = normalizedId;
        renderVehicleDetails(vehicle);
        if (Array.isArray(lastFilteredVehicles)) {
            const ids =
                lastHighlightedIds instanceof Set ? lastHighlightedIds : new Set();
            updateTable(lastFilteredVehicles, ids);
        }
        const updatedRow = document.querySelector(
            `#vehicle-table tbody tr[data-vehicle-id="${normalizedId}"]`
        );
        if (updatedRow instanceof HTMLElement) {
            updatedRow.focus();
        }
    }

    function ensurePolyline(layer, coordinates, options) {
        if (!coordinates || coordinates.length < 2) {
            if (layer && map.hasLayer(layer)) {
                map.removeLayer(layer);
            }
            return null;
        }

        if (!layer) {
            return L.polyline(coordinates, options).addTo(map);
        }

        layer.setLatLngs(coordinates);
        layer.setStyle(options);
        if (!map.hasLayer(layer)) {
            layer.addTo(map);
        }
        return layer;
    }

    function renderLegend(legendConfig) {
        const container = document.getElementById("map-legend");
        if (!container) {
            return;
        }
        if (
            !legendConfig
            || (!Array.isArray(legendConfig.routes)
                && !Array.isArray(legendConfig.traffic)
                && !Array.isArray(legendConfig.geofences))
        ) {
            container.innerHTML = "";
            container.setAttribute("aria-hidden", "true");
            return;
        }

        const sections = [];
        if (Array.isArray(legendConfig.routes) && legendConfig.routes.length) {
            const rows = legendConfig.routes
                .map((entry) => {
                    const color = entry.color || "#2563eb";
                    const label = entry.name || "Route";
                    return `<div class="legend-item"><span class="legend-color" style="background:${color};"></span><span>${label}</span></div>`;
                })
                .join("");
            sections.push(`<div class="legend-section"><h4>Routes</h4>${rows}</div>`);
        }
        if (Array.isArray(legendConfig.traffic) && legendConfig.traffic.length) {
            const rows = legendConfig.traffic
                .map((entry) => {
                    const color = entry.color || "#ef4444";
                    const label = entry.label || "Traffic";
                    return `<div class="legend-item"><span class="legend-color" style="background:${color};"></span><span>${label}</span></div>`;
                })
                .join("");
            sections.push(`<div class="legend-section"><h4>Traffic</h4>${rows}</div>`);
        }
        if (Array.isArray(legendConfig.geofences) && legendConfig.geofences.length) {
            const rows = legendConfig.geofences
                .map((entry) => {
                    const color = entry.color || "#f97316";
                    const label = entry.name || "Zone";
                    return `<div class="legend-item"><span class="legend-color" style="background:${color};"></span><span>${label}</span></div>`;
                })
                .join("");
            sections.push(`<div class="legend-section"><h4>Geofences</h4>${rows}</div>`);
        }

        container.innerHTML = sections.join("");
        container.setAttribute("aria-hidden", sections.length ? "false" : "true");
    }

    function renderGeofences(features) {
        geofenceLayer.clearLayers();
        if (!Array.isArray(features) || !features.length) {
            return;
        }
        features.forEach((feature) => {
            const coordinates = toLatLngs(feature.points || []);
            if (!coordinates.length) {
                return;
            }
            const polygon = L.polygon(coordinates, {
                color: feature.color || "#f97316",
                weight: 2,
                opacity: 0.65,
                fillColor: feature.color || "#f97316",
                fillOpacity: 0.12,
            })
                .bindTooltip(feature.name || "Geofence");
            polygon.addTo(geofenceLayer);
            if (polygon.bringToBack) {
                polygon.bringToBack();
            }
        });
    }

    function renderDepots(depots) {
        depotLayer.clearLayers();
        if (!Array.isArray(depots) || !depots.length) {
            return;
        }
        depots.forEach((depot) => {
            if (!depot || !depot.location) {
                return;
            }
            const marker = L.circleMarker(
                [depot.location.lat, depot.location.lng],
                {
                    radius: 7,
                    color: "#facc15",
                    fillColor: "#facc15",
                    fillOpacity: 0.85,
                    weight: 2,
                }
            );
            const capacity = typeof depot.capacity === "number"
                ? `Capacity: ${depot.capacity}`
                : null;
            const tooltip = [depot.name || "Depot", capacity]
                .filter(Boolean)
                .join("<br>");
            marker.bindTooltip(tooltip).addTo(depotLayer);
        });
    }

    function setLayerVisibility(layer, enabled) {
        if (enabled) {
            if (!map.hasLayer(layer)) {
                map.addLayer(layer);
            }
        } else if (map.hasLayer(layer)) {
            map.removeLayer(layer);
        }
    }

    function registerOverlayControls() {
        const overlayInputs = document.querySelectorAll(
            "#overlay-controls input[type='checkbox']"
        );
        overlayInputs.forEach((input) => {
            const key = input.dataset.overlay;
            if (!key) {
                return;
            }
            overlayState[key] = input.checked;
            const layer =
                key === "geofences"
                    ? geofenceLayer
                    : key === "depots"
                    ? depotLayer
                    : trafficLayer;
            setLayerVisibility(layer, overlayState[key]);
            input.addEventListener("change", () => {
                overlayState[key] = input.checked;
                setLayerVisibility(layer, overlayState[key]);
            });
        });
    }

    function buildPopup(vehicle) {
        const routeName = vehicle.route?.name || vehicle.fleet_area;
        const legOrigin = vehicle.route?.origin?.label;
        const legDestination = vehicle.route?.destination?.label;
        const etaText =
            typeof vehicle.eta_minutes === "number"
                ? `${vehicle.eta_minutes} min`
                : "—";
        const identifiers = vehicle.identifiers || {};
        const parts = [
            `<strong>${vehicle.name}</strong>`,
            routeName ? `Route: ${routeName}` : null,
            legOrigin || legDestination
                ? `Leg: ${legOrigin || "Origin"} → ${legDestination || "Destination"}`
                : null,
            identifiers.license_plate
                ? `Plate: ${identifiers.license_plate}`
                : null,
            identifiers.driver ? `Driver: ${identifiers.driver}` : null,
            identifiers.device_id ? `Device: ${identifiers.device_id}` : null,
            identifiers.vehicle_type
                ? `Vehicle: ${identifiers.vehicle_type}`
                : null,
            `Status: ${vehicle.status}`,
            `Speed: ${vehicle.speed_kmh} km/h`,
            `ETA: ${etaText}`,
            `Heading: ${vehicle.heading}°`,
        ];
        return parts.filter(Boolean).join("<br>");
    }

    function renderTraffic(features) {
        trafficLayer.clearLayers();
        if (!Array.isArray(features) || !features.length) {
            setLayerVisibility(trafficLayer, overlayState.traffic);
            return;
        }

        features.forEach((feature) => {
            if (!feature || !feature.coordinates) {
                return;
            }
            const severityColor = resolveTrafficColor(feature.severity);
            const coordinates = feature.coordinates.map((point) => {
                if (Array.isArray(point) && point.length >= 2) {
                    return [point[1], point[0]];
                }
                return point;
            });

            if (feature.type === "Point") {
                L.circleMarker(coordinates[0], {
                    radius: 6,
                    color: severityColor,
                    fillColor: severityColor,
                    fillOpacity: 0.6,
                    weight: 2,
                })
                    .bindTooltip(feature.description || "Traffic update")
                    .addTo(trafficLayer);
                return;
            }

            L.polyline(coordinates, {
                color: severityColor,
                weight: 5,
                opacity: 0.7,
            })
                .bindTooltip(feature.description || "Traffic update")
                .addTo(trafficLayer);
        });
        setLayerVisibility(trafficLayer, overlayState.traffic);
    }

    function updateTrafficMeta(meta) {
        const label = document.getElementById("traffic-meta");
        if (!label) {
            return;
        }
        if (!meta || !meta.generated) {
            label.textContent = "Traffic source: unavailable";
            return;
        }

        const generatedTime = new Date(meta.generated);
        const readable = Number.isNaN(generatedTime.getTime())
            ? meta.generated
            : generatedTime.toLocaleString();
        label.textContent = `Traffic source: ${meta.source || "unknown"} - refreshed ${readable}`;
    }

    function applyFilters(vehicles) {
        const term = typeof searchTerm === "string" ? searchTerm.trim().toLowerCase() : "";
        const digitsTerm = term.replace(/\D+/g, "");

        return vehicles.filter((vehicle) => {
            const statusMatch =
                !filterState.status || vehicle.status === filterState.status;
            const fleetMatch =
                !filterState.fleet_area ||
                vehicle.fleet_area === filterState.fleet_area;

            let searchMatch = true;
            if (term) {
                const identifiers = vehicle.identifiers || {};
                const candidates = [
                    vehicle.name,
                    identifiers.driver,
                    identifiers.vehicle_type,
                    identifiers.license_plate,
                    identifiers.device_id,
                    vehicle.fleet_area,
                ];

                searchMatch = candidates.some((value) =>
                    typeof value === "string" && value.toLowerCase().includes(term)
                );

                if (!searchMatch && digitsTerm) {
                    const phoneDigits = (identifiers.driver_phone || "").replace(/\D+/g, "");
                    searchMatch = phoneDigits.includes(digitsTerm);
                }
            }

            return statusMatch && fleetMatch && searchMatch;
        });
    }

    function updateTimestampLabel(timestamp) {
        const label = document.getElementById("last-updated");
        if (!label) {
            return;
        }

        let display = timestamp;
        const parsed = Date.parse(timestamp);
        if (!Number.isNaN(parsed)) {
            display = new Date(parsed).toLocaleString();
        }
        label.textContent = `Last update: ${display}`;
    }

    function updateTable(vehicles, highlightedIds) {
        const tableBody = document.querySelector("#vehicle-table tbody");
        if (!tableBody) {
            return;
        }
        const ids = highlightedIds instanceof Set ? highlightedIds : new Set();

        if (!vehicles.length) {
            tableBody.innerHTML =
                '<tr><td colspan="5">No vehicles match the selected filters.</td></tr>';
            selectedVehicleId = null;
            renderVehicleDetails(null);
            return;
        }

        const rows = vehicles
            .map((vehicle) => {
                const isHighlighted = ids.has(vehicle.id);
                const isSelected = vehicle.id === selectedVehicleId;
                const routeName =
                    vehicle.route?.name || vehicle.fleet_area || "—";
                const speedText =
                    typeof vehicle.speed_kmh === "number"
                        ? vehicle.speed_kmh.toFixed(1)
                        : "—";
                const etaText =
                    typeof vehicle.eta_minutes === "number"
                        ? vehicle.eta_minutes.toFixed(1)
                        : null;
                const routeCell = etaText
                    ? `${routeName}<span class="table-eta">ETA ${etaText} min</span>`
                    : routeName;
                const driverName =
                    vehicle.identifiers?.driver && vehicle.identifiers.driver.trim()
                        ? vehicle.identifiers.driver
                        : "—";
                const rowClasses = [
                    isHighlighted ? "highlight" : "",
                    isSelected ? "is-selected" : "",
                ]
                    .filter(Boolean)
                    .join(" ");
                return `
            <tr data-vehicle-id="${vehicle.id}" class="${rowClasses}" tabindex="0" aria-selected="${isSelected ? "true" : "false"}">
                <td>${vehicle.name}</td>
                <td>${driverName}</td>
                <td>${vehicle.status}</td>
                <td>${speedText}</td>
                <td>${routeCell}</td>
            </tr>`;
            })
            .join("");

        tableBody.innerHTML = rows;
        tableBody
            .querySelectorAll("tr[data-vehicle-id]")
            .forEach((row) => {
                const vehicleId = Number(row.dataset.vehicleId);
                if (!Number.isFinite(vehicleId)) {
                    return;
                }
                row.addEventListener("click", () => {
                    selectVehicle(vehicleId);
                });
                row.addEventListener("keydown", (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        selectVehicle(vehicleId);
                    }
                });
            });
    }

    function updateMapLayers(allVehicles, highlightedIds) {
        const activeIds = new Set();

        allVehicles.forEach((vehicle) => {
            const id = vehicle.id;
            const latLng = [vehicle.location.lat, vehicle.location.lng];
            const color =
                vehicle.route?.color ||
                resolveColor(vehicle.fleet_area || vehicle.route?.name || "");
            const isHighlighted = highlightedIds.has(id);
            const existing = trackedLayers.get(id);
            const trailCoords = toLatLngs(vehicle.trail);
            const upcomingCoords = toLatLngs(vehicle.upcoming);
            const fullRouteCoords = toLatLngs(vehicle.path);
            const routeCoords =
                upcomingCoords.length >= 2 ? upcomingCoords : fullRouteCoords;

            const trailOptions = {
                color,
                weight: isHighlighted ? 6 : 4,
                opacity: isHighlighted ? 0.9 : 0.55,
                lineCap: "round",
            };
            const routeOptions = {
                color,
                weight: 3,
                opacity: isHighlighted ? 0.65 : 0.3,
                dashArray: "8 10",
            };

            if (!existing) {
                const marker = L.circleMarker(latLng, {
                    radius: isHighlighted ? 9 : 7.5,
                    color,
                    weight: 2,
                    fillColor: color,
                    fillOpacity: isHighlighted ? 0.95 : 0.5,
                    opacity: isHighlighted ? 1 : 0.6,
                });
                vehicleCluster.addLayer(marker);

                marker.bindPopup(buildPopup(vehicle));

                const trailLine = ensurePolyline(null, trailCoords, trailOptions);
                const routeLine = ensurePolyline(null, routeCoords, routeOptions);

                trackedLayers.set(id, { marker, trailLine, routeLine });
            } else {
                existing.marker.setLatLng(latLng);
                existing.marker.setStyle({
                    color,
                    fillColor: color,
                    fillOpacity: isHighlighted ? 0.95 : 0.5,
                    opacity: isHighlighted ? 1 : 0.6,
                });
                existing.marker.setRadius(isHighlighted ? 9 : 7.5);
                existing.marker.setPopupContent(buildPopup(vehicle));

                existing.trailLine = ensurePolyline(
                    existing.trailLine,
                    trailCoords,
                    trailOptions
                );
                existing.routeLine = ensurePolyline(
                    existing.routeLine,
                    routeCoords,
                    routeOptions
                );
            }

            activeIds.add(id);
        });

        trackedLayers.forEach((layer, id) => {
            if (!activeIds.has(id)) {
                vehicleCluster.removeLayer(layer.marker);
                if (layer.trailLine) {
                    map.removeLayer(layer.trailLine);
                }
                if (layer.routeLine) {
                    map.removeLayer(layer.routeLine);
                }
                trackedLayers.delete(id);
            }
        });

        if (!hasFitBounds && allVehicles.length) {
            const bounds = L.latLngBounds(
                allVehicles.map((vehicle) => [
                    vehicle.location.lat,
                    vehicle.location.lng,
                ])
            );
            map.fitBounds(bounds, { padding: [40, 40] });
            hasFitBounds = true;
        }
    }

    function refreshInterface(timestamp) {
        const highlightedVehicles = applyFilters(latestVehicles);
        const highlightedIds = new Set(highlightedVehicles.map((v) => v.id));

        if (selectedVehicleId !== null && !highlightedIds.has(selectedVehicleId)) {
            selectedVehicleId = null;
            renderVehicleDetails(null);
        }

        lastFilteredVehicles = highlightedVehicles;
        lastHighlightedIds = highlightedIds;

        updateMapLayers(latestVehicles, highlightedIds);
        updateTable(highlightedVehicles, highlightedIds);

        if (selectedVehicleId !== null) {
            const selectedVehicle = findVehicleById(selectedVehicleId);
            if (selectedVehicle) {
                renderVehicleDetails(selectedVehicle);
            } else {
                selectedVehicleId = null;
                renderVehicleDetails(null);
            }
        }

        if (timestamp) {
            updateTimestampLabel(timestamp);
        }
    }

    function registerFilters() {
        document.querySelectorAll(".filter-group").forEach((group) => {
            group.addEventListener("click", (event) => {
                const target = event.target;
                if (!(target instanceof HTMLElement)) {
                    return;
                }
                if (!target.classList.contains("filter-button")) {
                    return;
                }

                group.querySelectorAll(".filter-button").forEach((button) => {
                    button.classList.remove("is-active");
                });
                target.classList.add("is-active");

                const filterKey = group.dataset.filterType;
                if (filterKey && Object.prototype.hasOwnProperty.call(filterState, filterKey)) {
                    filterState[filterKey] = target.dataset.filter || "";
                }

                refreshInterface();
            });
        });
    }

    function registerSearch() {
        if (!searchInput) {
            return;
        }
        let debounceId = null;
        const handleInput = () => {
            searchTerm = searchInput.value || "";
            refreshInterface();
        };
        searchInput.addEventListener("input", () => {
            if (debounceId) {
                window.clearTimeout(debounceId);
            }
            debounceId = window.setTimeout(handleInput, 120);
        });
        searchInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                if (debounceId) {
                    window.clearTimeout(debounceId);
                }
                handleInput();
            }
        });
    }

    const POLL_INTERVAL_MS = 5000;
    let pollTimeoutId = null;
    const TRAFFIC_POLL_MS = 60000;
    let trafficTimeoutId = null;

    async function pollVehicles() {
        try {
            const response = await fetch("/api/vehicles/");
            if (!response.ok) {
                throw new Error(`Bad response: ${response.status}`);
            }

            const payload = await response.json();
            latestVehicles = Array.isArray(payload.vehicles)
                ? payload.vehicles
                : [];
            refreshInterface(payload.timestamp);
        } catch (error) {
            console.warn("Vehicle poll failed; retrying later.", error);
        } finally {
            pollTimeoutId = window.setTimeout(pollVehicles, POLL_INTERVAL_MS);
        }
    }

    async function pollTraffic() {
        try {
            const response = await fetch("/api/traffic/");
            if (!response.ok) {
                throw new Error(`Bad response: ${response.status}`);
            }

            const payload = await response.json();
            renderTraffic(payload.features || []);
            updateTrafficMeta(payload);
        } catch (error) {
            console.warn("Traffic poll failed; retrying later.", error);
        } finally {
            trafficTimeoutId = window.setTimeout(pollTraffic, TRAFFIC_POLL_MS);
        }
    }

    renderGeofences(initialGeofences);
    renderDepots(initialDepots);
    renderLegend(legendData);
    registerOverlayControls();
    registerFilters();
    registerSearch();
    refreshInterface(initialTimestamp);
    renderTraffic(initialTrafficFeatures);
    updateTrafficMeta(initialTrafficMeta);
    pollTimeoutId = window.setTimeout(pollVehicles, POLL_INTERVAL_MS);
    trafficTimeoutId = window.setTimeout(pollTraffic, 2000);

    window.addEventListener("beforeunload", () => {
        if (pollTimeoutId) {
            window.clearTimeout(pollTimeoutId);
        }
        if (trafficTimeoutId) {
            window.clearTimeout(trafficTimeoutId);
        }
    });
})();
