import heapq
from shapely.geometry import LineString, Point
from .services import decode_polyline6, haversine_km

class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = {}
        self.distances = {}

    def add_node(self, value):
        self.nodes.add(value)
        if value not in self.edges:
            self.edges[value] = []

    def add_edge(self, from_node, to_node, distance):
        self.edges[from_node].append(to_node)
        self.distances[(from_node, to_node)] = distance

def astar(graph, start, end, heuristic):
    priority_queue = [(0, start)]
    visited = {start: 0}
    path = {}

    while priority_queue:
        current_cost, current_node = heapq.heappop(priority_queue)

        if current_node == end:
            break

        for neighbor in graph.edges[current_node]:
            cost = graph.distances[(current_node, neighbor)]
            new_cost = visited[current_node] + cost
            if neighbor not in visited or new_cost < visited[neighbor]:
                visited[neighbor] = new_cost
                priority = new_cost + heuristic(neighbor, end)
                heapq.heappush(priority_queue, (priority, neighbor))
                path[neighbor] = current_node

    return visited, path

import logging

logger = logging.getLogger(__name__)

def build_graph_from_routes(route_definitions):
    graph = Graph()
    polylines = []
    for route in route_definitions:
        decoded_polyline = decode_polyline6(route["polyline"])
        for point in decoded_polyline:
            graph.add_node(point)
        polylines.append(LineString(decoded_polyline))

    logger.info(f"Number of nodes in graph: {len(graph.nodes)}")

    for polyline in polylines:
        for i in range(len(polyline.coords) - 1):
            node1 = polyline.coords[i]
            node2 = polyline.coords[i+1]
            distance = haversine_km(node1, node2)
            graph.add_edge(node1, node2, distance)
            graph.add_edge(node2, node1, distance)

    return graph
