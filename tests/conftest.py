"""Shared pytest fixtures.

Layout mirrors the package: tests/unit (nodes, routing, retriever with the fake LLM),
tests/api (HTTP via TestClient), tests/integration (real PostgreSQL, marked `integration`).
Tests never call a real LLM.
"""
