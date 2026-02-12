#!/Users/pierre.cariou/Code/onboarding-analytics/.venv/bin/python
"""
Metabase Collection Operations

Provides post and put operations for Metabase collections.

Example:
    # Create a new collection
    from libs.metabase.collection import post_collection
    new_collection = post_collection("My Collection", parent_id=123)
    
    # Update a collection
    from libs.metabase.collection import put_collection
    updated = put_collection(456, name="Renamed Collection")
"""

import json
from typing import Dict, Any, Optional
import urllib.error

from .utils import get_metabase_config, api_request


def get_collection(collection_id: int) -> Optional[Dict[str, Any]]:
    """
    Get collection information from Metabase.
    
    Args:
        collection_id: Collection ID to check
    
    Returns:
        Collection data if exists, None if not found
    """
    config = get_metabase_config()
    url = f"{config['url']}/api/collection/{collection_id}"
    
    try:
        return api_request(url, config['api_key'], method="GET")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def post_collection(name: str, parent_id: int, description: str = None) -> Dict[str, Any]:
    """
    Create a new collection in Metabase.
    
    Args:
        name: Collection name
        parent_id: Parent collection ID
        description: Optional collection description
    
    Returns:
        Created collection data (includes new ID)
    
    Raises:
        urllib.error.HTTPError: If request fails
        
    See: https://www.metabase.com/docs/latest/api#tag/apicollection/post/api/collection
    """
    config = get_metabase_config()
    url = f"{config['url']}/api/collection"
    
    collection_data = {
        "name": name,
        "parent_id": parent_id,
    }
    
    if description:
        collection_data["description"] = description
    
    return api_request(url, config['api_key'], method="POST", data=collection_data)


def put_collection(collection_id: int, name: Optional[str] = None, 
                   description: Optional[str] = None, parent_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Update a collection in Metabase.
    
    Args:
        collection_id: Collection ID to update
        name: Optional new name
        description: Optional new description
        parent_id: Optional new parent collection ID
    
    Returns:
        Updated collection data
    
    Raises:
        urllib.error.HTTPError: If request fails
        
    See: https://www.metabase.com/docs/latest/api#tag/apicollection/put/api/collection/{id}
    """
    config = get_metabase_config()
    url = f"{config['url']}/api/collection/{collection_id}"
    
    collection_data = {}
    
    if name is not None:
        collection_data["name"] = name
    
    if description is not None:
        collection_data["description"] = description
    
    if parent_id is not None:
        collection_data["parent_id"] = parent_id
    
    return api_request(url, config['api_key'], method="PUT", data=collection_data)
