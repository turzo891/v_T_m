(function () {
    "use strict";

    const mapContainer = document.getElementById("map");
    if (!mapContainer || typeof window.L === "undefined") {
        return;
    }

    const detailCard = document.getElementById("vehicle-detail-card");
    const detailTitle = document.getElementById("vehicle-detail-title");
    const detailEmpty = document.getElementById("vehicle-detail-empty");
    const detailGrid = document.getElementById("vehicle-detail-grid");
    const detailDriver = document.getElementById("vehicle-detail-driver");
    const detailMobile = document.getElementById("vehicle-detail-mobile");
    const detailLicense = document.getElementById("vehicle-detail-license");
    const detailHistory = document.getElementById("vehicle-detail-history");
    const detailHistoryList = document.getElementById("vehicle-detail-history-list");
    if (detailTitle) {
        detailTitle.hidden = true;
    }
    if (detailCard && !detailCard.hasAttribute("tabindex")) {
        detailCard.setAttribute("tabindex", "-1");
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

    const mapZoom = typeof center.zoom === "number" ? center.zoom : 12;
    const map = L.map(mapContainer).setView([center.lat, center.lng], mapZoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
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
        search: "",
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
    let selectedVehicleId = null;

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
            identifiers.driver_mobile
                ? `Mobile: ${identifiers.driver_mobile}`
                : null,
            identifiers.driver_license
                ? `License: ${identifiers.driver_license}`
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

    function renderVehicleDetails(vehicle) {
        if (!detailCard || !detailEmpty || !detailGrid) {
            return;
        }
        if (!vehicle) {
            if (detailTitle) {
                detailTitle.textContent = "";
                detailTitle.hidden = true;
            }
            detailEmpty.hidden = false;
            detailGrid.hidden = true;
            if (detailHistory) {
                detailHistory.hidden = true;
            }
            if (detailDriver) {
                detailDriver.textContent = "—";
            }
            if (detailMobile) {
                detailMobile.textContent = "—";
            }
            if (detailLicense) {
                detailLicense.textContent = "—";
            }
            if (detailHistoryList) {
                detailHistoryList.innerHTML = "";
            }
            return;
        }

        if (detailTitle) {
            detailTitle.textContent = `${vehicle.name} • ${vehicle.fleet_area}`;
            detailTitle.hidden = false;
        }
        detailEmpty.hidden = true;
        detailGrid.hidden = false;

        if (detailDriver) {
            detailDriver.textContent = vehicle.identifiers?.driver || "—";
        }
        if (detailMobile) {
            detailMobile.textContent = vehicle.identifiers?.driver_mobile || "—";
        }
        if (detailLicense) {
            detailLicense.textContent = vehicle.identifiers?.driver_license || "—";
        }

        if (detailHistory && detailHistoryList) {
            const history = Array.isArray(vehicle.route_history)
                ? vehicle.route_history
                : [];
            if (history.length) {
                detailHistory.hidden = false;
                detailHistoryList.innerHTML = history
                    .map((entry) => `<li>${entry}</li>`)
                    .join("");
            } else {
                detailHistory.hidden = false;
                detailHistoryList.innerHTML =
                    "<li>No route history available.</li>";
            }
        }
    }

    function registerTableInteractions() {
        const tableBody = document.querySelector("#vehicle-table tbody");
        if (!tableBody) {
            return;
        }
        tableBody.querySelectorAll("tr[data-vehicle-id]").forEach((row) => {
            const vehicleId = Number(row.dataset.vehicleId);
            if (!Number.isFinite(vehicleId)) {
                return;
            }
            const handleSelect = () => {
                selectVehicle(vehicleId);
            };
            row.addEventListener("click", handleSelect);
            row.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    handleSelect();
                }
            });
            const button = row.querySelector(".vehicle-select-button");
            if (button) {
                button.addEventListener("click", (event) => {
                    event.stopPropagation();
                    handleSelect();
                });
            }
        });
    }

    function focusTableRow(vehicleId) {
        const selector = `#vehicle-table tbody tr[data-vehicle-id="${vehicleId}"]`;
        const row = document.querySelector(selector);
        if (!row) {
            return;
        }
        if (typeof row.scrollIntoView === "function") {
            row.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
        if (typeof row.focus === "function") {
            window.requestAnimationFrame(() => {
                row.focus();
            });
        }
    }

    function focusDetailCard() {
        if (!detailCard) {
            return;
        }
        if (typeof detailCard.scrollIntoView === "function") {
            detailCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
        const focusTarget =
            detailCard.querySelector(".vehicle-select-button") ||
            detailCard.querySelector("button") ||
            detailCard;
        if (focusTarget && typeof focusTarget.focus === "function") {
            window.requestAnimationFrame(() => {
                focusTarget.focus({ preventScroll: true });
            });
        }
    }

    function selectVehicle(vehicleId, options = {}) {
        const { focusTable = false } = options;
        const numericId = Number(vehicleId);
        if (!Number.isFinite(numericId)) {
            return;
        }
        const vehicle = latestVehicles.find((entry) => entry.id === numericId);
        if (!vehicle) {
            if (selectedVehicleId !== null) {
                selectedVehicleId = null;
                renderVehicleDetails(null);
                refreshInterface();
            }
            return;
        }
        if (selectedVehicleId === numericId) {
            renderVehicleDetails(vehicle);
            if (focusTable) {
                focusTableRow(numericId);
            }
            return;
        }
        selectedVehicleId = numericId;
        renderVehicleDetails(vehicle);
        refreshInterface();
        if (focusTable) {
            focusTableRow(numericId);
        }
        focusDetailCard();
    }

    function matchesSearch(vehicle) {
        if (!filterState.search) {
            return true;
        }
        const identifiers = vehicle.identifiers || {};
        const fields = [
            vehicle.name,
            identifiers.license_plate,
            identifiers.driver,
            identifiers.device_id,
            identifiers.vehicle_type,
        ];
        return fields
            .filter((value) => typeof value === "string" && value)
            .some((value) =>
                value.toLowerCase().includes(filterState.search)
            );
    }

    function applyFilters(vehicles) {
        return vehicles.filter((vehicle) => {
            const statusMatch =
                !filterState.status || vehicle.status === filterState.status;
            const fleetMatch =
                !filterState.fleet_area ||
                vehicle.fleet_area === filterState.fleet_area;
            const searchMatch = matchesSearch(vehicle);
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

    function updateRouteFilterButtons(selectedValue) {
        const routeGroup = document.querySelector(
            ".filter-group[data-filter-type='fleet_area']"
        );
        if (!routeGroup) {
            return;
        }
        const normalized = selectedValue || "";
        routeGroup.querySelectorAll(".filter-button").forEach((button) => {
            const buttonValue = button.dataset.filter || "";
            if (!normalized) {
                button.classList.remove("is-hidden");
                return;
            }
            if (buttonValue === normalized || buttonValue === "") {
                button.classList.remove("is-hidden");
            } else {
                button.classList.add("is-hidden");
            }
        });
    }

    function updateTable(vehicles, visibleIds) {
        const tableBody = document.querySelector("#vehicle-table tbody");
        if (!tableBody) {
            return;
        }

        if (!vehicles.length) {
            tableBody.innerHTML =
                '<tr><td colspan="4">No vehicles match the selected filters.</td></tr>';
            return;
        }

        const rows = vehicles
            .map((vehicle) => {
                const isHighlighted = visibleIds.has(vehicle.id);
                const isSelected = selectedVehicleId === vehicle.id;
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
                const classNames = [
                    isHighlighted ? "highlight" : "",
                    isSelected ? "is-selected" : "",
                ]
                    .filter(Boolean)
                    .join(" ");
                const ariaSelected = isSelected ? "true" : "false";
                const selectButton = `<button type="button" class="vehicle-select-button" data-vehicle-id="${vehicle.id}">${vehicle.name}</button>`;
                return `
            <tr class="${classNames}" data-vehicle-id="${vehicle.id}" role="button" tabindex="0" aria-selected="${ariaSelected}">
                <td>${selectButton}</td>
                <td>${vehicle.status}</td>
                <td>${speedText}</td>
                <td>${routeCell}</td>
            </tr>`;
            })
            .join("");

        tableBody.innerHTML = rows;
        registerTableInteractions();
    }

    function updateMapLayers(allVehicles, visibleIds) {
        const activeIds = new Set();
        const isFilteredView =
            visibleIds.size > 0 && visibleIds.size !== allVehicles.length;

        allVehicles.forEach((vehicle) => {
            const id = vehicle.id;
            const shouldDisplay = visibleIds.has(id);
            const latLng = [vehicle.location.lat, vehicle.location.lng];
            const color =
                vehicle.route?.color ||
                resolveColor(vehicle.fleet_area || vehicle.route?.name || "");
            const existing = trackedLayers.get(id);
            const trailCoords = toLatLngs(vehicle.trail);
            const upcomingCoords = toLatLngs(vehicle.upcoming);
            const fullRouteCoords = toLatLngs(vehicle.path);
            const routeCoords =
                upcomingCoords.length >= 2 ? upcomingCoords : fullRouteCoords;
            const isSelected = selectedVehicleId === id;
            const emphasise = isFilteredView || isSelected;

            if (!shouldDisplay) {
                if (existing) {
                    vehicleCluster.removeLayer(existing.marker);
                    if (existing.trailLine) {
                        map.removeLayer(existing.trailLine);
                    }
                    if (existing.routeLine) {
                        map.removeLayer(existing.routeLine);
                    }
                    trackedLayers.delete(id);
                }
                return;
            }

            const trailOptions = {
                color,
                weight: isSelected ? 7 : emphasise ? 6 : 4,
                opacity: isSelected ? 0.95 : emphasise ? 0.9 : 0.55,
                lineCap: "round",
            };
            const routeOptions = {
                color,
                weight: isSelected ? 4 : 3,
                opacity: isSelected ? 0.8 : emphasise ? 0.65 : 0.3,
                dashArray: "8 10",
            };

            if (!existing) {
                const marker = L.circleMarker(latLng, {
                    radius: isSelected ? 10.5 : emphasise ? 9 : 7.5,
                    color,
                    weight: 2,
                    fillColor: color,
                    fillOpacity: isSelected ? 1 : emphasise ? 0.95 : 0.5,
                    opacity: isSelected ? 1 : emphasise ? 1 : 0.6,
                });
                marker.on("click", () => {
                    selectVehicle(vehicle.id, { focusTable: true });
                });
                vehicleCluster.addLayer(marker);

                marker.bindPopup(buildPopup(vehicle));
                if (isSelected && typeof marker.bringToFront === "function") {
                    marker.bringToFront();
                }

                const trailLine = ensurePolyline(null, trailCoords, trailOptions);
                const routeLine = ensurePolyline(null, routeCoords, routeOptions);

                trackedLayers.set(id, { marker, trailLine, routeLine });
            } else {
                existing.marker.setLatLng(latLng);
                existing.marker.setStyle({
                    color,
                    fillColor: color,
                    fillOpacity: isSelected ? 1 : emphasise ? 0.95 : 0.5,
                    opacity: isSelected ? 1 : emphasise ? 1 : 0.6,
                });
                existing.marker.setRadius(
                    isSelected ? 10.5 : emphasise ? 9 : 7.5
                );
                existing.marker.setPopupContent(buildPopup(vehicle));
                if (isSelected && typeof existing.marker.bringToFront === "function") {
                    existing.marker.bringToFront();
                }

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
        const filteredVehicles = applyFilters(latestVehicles);
        const visibleIds = new Set(filteredVehicles.map((v) => v.id));

        if (
            selectedVehicleId !== null &&
            !visibleIds.has(selectedVehicleId)
        ) {
            selectedVehicleId = null;
            renderVehicleDetails(null);
        } else if (selectedVehicleId !== null) {
            const selectedVehicle = latestVehicles.find(
                (vehicle) => vehicle.id === selectedVehicleId
            );
            if (selectedVehicle) {
                renderVehicleDetails(selectedVehicle);
            }
        }

        updateMapLayers(latestVehicles, visibleIds);
        updateTable(filteredVehicles, visibleIds);

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
                const newValue = target.dataset.filter || "";
                let shouldRefresh = true;
                if (
                    filterKey &&
                    Object.prototype.hasOwnProperty.call(filterState, filterKey)
                ) {
                    const previousValue = filterState[filterKey];
                    if (previousValue === newValue) {
                        shouldRefresh = false;
                    } else {
                        filterState[filterKey] = newValue;
                        selectedVehicleId = null;
                        renderVehicleDetails(null);
                    }
                }

                if (!filterKey) {
                    return;
                }

                if (filterKey === "fleet_area") {
                    updateRouteFilterButtons(filterState.fleet_area);
                }

                if (shouldRefresh) {
                    refreshInterface();
                }
            });
        });

        updateRouteFilterButtons(filterState.fleet_area);
    }

    function registerSearchControl() {
        const searchInput = document.getElementById("vehicle-search");
        if (!searchInput) {
            return;
        }
        if (filterState.search) {
            searchInput.value = filterState.search;
        }
        let debounceId = null;
        searchInput.addEventListener("input", () => {
            if (debounceId) {
                window.clearTimeout(debounceId);
            }
            debounceId = window.setTimeout(() => {
                filterState.search = searchInput.value.trim().toLowerCase();
                refreshInterface();
            }, 150);
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
    registerSearchControl();
    registerFilters();
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
