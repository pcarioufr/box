"""Excalidraw Canvas Server API client."""

import requests
from typing import Optional

DEFAULT_BASE_URL = "http://localhost:3000"


class ExcalidrawAPI:
    """Client for the Excalidraw Canvas Server REST API."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip('/')

    def health(self) -> dict:
        """Check server health."""
        resp = requests.get(f"{self.base_url}/health")
        resp.raise_for_status()
        return resp.json()

    def get_elements(self) -> list[dict]:
        """Get all elements on the canvas."""
        resp = requests.get(f"{self.base_url}/api/elements")
        resp.raise_for_status()
        data = resp.json()
        return data.get("elements", [])

    def create_elements(self, elements: list[dict]) -> list[dict]:
        """Create multiple elements on the canvas (batch)."""
        resp = requests.post(
            f"{self.base_url}/api/elements/batch",
            json={"elements": elements},
            headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
        return resp.json().get("elements", [])

    def update_element(self, element_id: str, updates: dict) -> dict:
        """Update a single element by ID (merge update)."""
        resp = requests.put(
            f"{self.base_url}/api/elements/{element_id}",
            json=updates,
            headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
        return resp.json().get("element", {})

    def delete_element(self, element_id: str) -> bool:
        """Delete a single element by ID."""
        resp = requests.delete(f"{self.base_url}/api/elements/{element_id}")
        resp.raise_for_status()
        return True

    def clear(self) -> int:
        """Clear all elements from the canvas. Returns count deleted."""
        count = len(self.get_elements())
        resp = requests.delete(f"{self.base_url}/api/elements")
        resp.raise_for_status()
        return count


def get_client(base_url: Optional[str] = None) -> ExcalidrawAPI:
    """Get an API client instance."""
    return ExcalidrawAPI(base_url or DEFAULT_BASE_URL)
