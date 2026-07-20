"""Agents-home voice/text router: detect which agent is being addressed.

Wiring (Factory) lives in build_router_strategy().
"""
from .classify import RouteStrategy, LettaAgentRouteStrategy, build_router_strategy

__all__ = ["RouteStrategy", "LettaAgentRouteStrategy", "build_router_strategy"]
