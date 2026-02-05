#!/usr/bin/env python3
"""Datadog Notebooks creation and update functionality using standard Datadog API format."""

import os
import json
import logging
from typing import Optional, Dict, Any
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.notebooks_api import NotebooksApi
from datadog_api_client.v1.model.notebook_create_request import NotebookCreateRequest
from datadog_api_client.v1.model.notebook_update_request import NotebookUpdateRequest

logger = logging.getLogger(__name__)


def create_notebook_from_json(
    notebook_def: Dict[str, Any],
    source_file: Optional[str] = None,
    update_source: bool = True
) -> str:
    """Create a Datadog notebook from a standard API JSON definition.

    Args:
        notebook_def: Notebook definition in standard Datadog API format
        source_file: Source JSON file path (to update with notebook ID)
        update_source: Whether to update the source file with the notebook ID (default: True)

    Returns:
        URL of the created notebook
    """
    # Get credentials from environment
    api_key = os.getenv("DD_API_KEY")
    app_key = os.getenv("DD_APP_KEY")
    dd_site = os.getenv("DD_SITE", "datadoghq.com")

    if not api_key or not app_key:
        raise ValueError(
            "Missing Datadog credentials. Set DD_API_KEY and DD_APP_KEY environment variables.\n"
            "Create API and App keys at: https://app.datadoghq.com/organization-settings/api-keys"
        )

    # Extract notebook name for logging
    notebook_name = "Unknown"
    try:
        notebook_name = notebook_def.get("data", {}).get("attributes", {}).get("name", "Unknown")
    except:
        pass

    logger.info(f"Creating notebook: {notebook_name}")
    logger.info(f"  Using standard Datadog API format")

    # Configure Datadog API client
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = api_key
    configuration.api_key["appKeyAuth"] = app_key
    configuration.server_variables["site"] = dd_site

    # Create notebook
    with ApiClient(configuration) as api_client:
        api_instance = NotebooksApi(api_client)

        try:
            # Create NotebookCreateRequest from the provided JSON
            # The API client will deserialize the dict into the proper model
            body = NotebookCreateRequest(**notebook_def)

            response = api_instance.create_notebook(body=body)

            # Extract notebook ID and build URL
            notebook_id = response.data.id
            notebook_url = f"https://app.{dd_site}/notebook/{notebook_id}"

            logger.info(f"✓ Notebook created successfully")
            logger.info(f"  ID: {notebook_id}")
            logger.info(f"  URL: {notebook_url}")

            # Update source file with notebook ID
            if update_source and source_file and source_file != '-':
                try:
                    # Add the notebook ID to the definition
                    if "data" not in notebook_def:
                        notebook_def["data"] = {}
                    notebook_def["data"]["id"] = notebook_id

                    # Write back to source file
                    with open(source_file, 'w') as f:
                        json.dump(notebook_def, f, indent=2)

                    logger.info(f"  Updated source file with notebook ID: {source_file}")
                except Exception as e:
                    logger.warning(f"  Failed to update source file: {e}")

            return notebook_url

        except Exception as e:
            logger.error(f"Failed to create notebook: {e}")
            raise


def update_notebook_from_json(
    notebook_def: Dict[str, Any],
    source_file: Optional[str] = None
) -> str:
    """Update an existing Datadog notebook from a standard API JSON definition.

    Args:
        notebook_def: Notebook definition in standard Datadog API format (must include data.id)
        source_file: Source JSON file path (for logging)

    Returns:
        URL of the updated notebook
    """
    # Get credentials from environment
    api_key = os.getenv("DD_API_KEY")
    app_key = os.getenv("DD_APP_KEY")
    dd_site = os.getenv("DD_SITE", "datadoghq.com")

    if not api_key or not app_key:
        raise ValueError(
            "Missing Datadog credentials. Set DD_API_KEY and DD_APP_KEY environment variables.\n"
            "Create API and App keys at: https://app.datadoghq.com/organization-settings/api-keys"
        )

    # Extract notebook ID
    notebook_id = notebook_def.get("data", {}).get("id")
    if not notebook_id:
        raise ValueError(
            "Notebook ID not found in JSON. The notebook must have been created first.\n"
            f"Expected: {{\"data\": {{\"id\": <notebook_id>, ...}}}}\n"
            f"To create a new notebook, use: datadog notebook create"
        )

    # Extract notebook name for logging
    notebook_name = "Unknown"
    try:
        notebook_name = notebook_def.get("data", {}).get("attributes", {}).get("name", "Unknown")
    except:
        pass

    logger.info(f"Updating notebook: {notebook_name}")
    logger.info(f"  ID: {notebook_id}")
    logger.info(f"  Using standard Datadog API format")

    # Configure Datadog API client
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = api_key
    configuration.api_key["appKeyAuth"] = app_key
    configuration.server_variables["site"] = dd_site

    # Update notebook
    with ApiClient(configuration) as api_client:
        api_instance = NotebooksApi(api_client)

        try:
            # Create NotebookUpdateRequest from the provided JSON
            # The API client will deserialize the dict into the proper model
            body = NotebookUpdateRequest(**notebook_def)

            response = api_instance.update_notebook(notebook_id=notebook_id, body=body)

            # Build URL
            notebook_url = f"https://app.{dd_site}/notebook/{notebook_id}"

            logger.info(f"✓ Notebook updated successfully")
            logger.info(f"  URL: {notebook_url}")

            return notebook_url

        except Exception as e:
            logger.error(f"Failed to update notebook: {e}")
            raise
