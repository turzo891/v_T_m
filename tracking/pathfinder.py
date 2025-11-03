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
        self.edges[value] = []

    def add_edge(self, from_node, to_node, distance):
        self.edges[from_node].append(to_node)
        self.distances[(from_node, to_node)] = distance

def dijkstra(graph, initial):
    visited = {initial: 0}
    path = {}

    nodes = set(graph.nodes)

    while nodes:
        min_node = None
        for node in nodes:
            if node in visited:
                if min_node is None:
                    min_node = node
                elif visited[node] < visited[min_node]:
                    min_node = node

        if min_node is None:
            break

        nodes.remove(min_node)
        current_weight = visited[min_node]

        for edge in graph.edges[min_node]:
            weight = current_weight + graph.distances[(min_node, edge)]
            if edge not in visited or weight < visited[edge]:
                visited[edge] = weight
                path[edge] = min_node

    return visited, path

import logging

logger = logging.getLogger(__name__)

def build_graph_from_routes(route_definitions):
    graph = Graph()
    polylines = []
    for route in route_definitions:
        decoded_polyline = decode_polyline6(route["polyline"])
        polylines.append(LineString(decoded_polyline))

    logger.info(f"Number of polylines: {len(polylines)}")

    for i in range(len(polylines)):
        for j in range(i + 1, len(polylines)):
            intersection = polylines[i].intersection(polylines[j])
            if not intersection.is_empty:
                logger.info(f"Intersection type: {intersection.geom_type}")
                if intersection.geom_type == 'Point':
                    graph.add_node(intersection.coords[0])
                elif intersection.geom_type == 'MultiPoint':
                    for point in intersection.geoms:
                        graph.add_node(point.coords[0])
                elif intersection.geom_type == 'LineString':
                    for coord in intersection.coords:
                        graph.add_node(coord)
                elif intersection.geom_type == 'MultiLineString':
                    for line in intersection.geoms:
                        for coord in line.coords:
                            graph.add_node(coord)

    logger.info(f"Number of nodes in graph: {len(graph.nodes)}")
    logger.info(f"Nodes: {graph.nodes}")

    for i in range(len(polylines)):
        for node in graph.nodes:
            if polylines[i].distance(Point(node)) < 1e-8:
                for other_node in graph.nodes:
                    if polylines[i].distance(Point(other_node)) < 1e-8 and node != other_node:
                        line = LineString([node, other_node])
                        if polylines[i].contains(line):
                            distance = haversine_km(node, other_node)
                            graph.add_edge(node, other_node, distance)

    return graph

class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = {}
        self.distances = {}

    def add_node(self, value):
        self.nodes.add(value)
        self.edges[value] = []

    def add_edge(self, from_node, to_node, distance):
        self.edges[from_node].append(to_node)
        self.distances[(from_node, to_node)] = distance

def dijkstra(graph, initial):
    visited = {initial: 0}
    path = {}

    nodes = set(graph.nodes)

    while nodes:
        min_node = None
        for node in nodes:
            if node in visited:
                if min_node is None:
                    min_node = node
                elif visited[node] < visited[min_node]:
                    min_node = node

        if min_node is None:
            break

        nodes.remove(min_node)
        current_weight = visited[min_node]

        for edge in graph.edges[min_node]:
            weight = current_weight + graph.distances[(min_node, edge)]
            if edge not in visited or weight < visited[edge]:
                visited[edge] = weight
                path[edge] = min_node

    return visited, path
