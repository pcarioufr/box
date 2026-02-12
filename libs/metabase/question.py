#!/Users/pierre.cariou/Code/onboarding-analytics/.venv/bin/python
"""
Metabase Question Operations

ORM-like interface for Metabase questions with local file management.

Example:
    # Create a new question
    question = Question(Path("questions/my-question.yaml"))
    question_id = question.post(collection_id=123, database_id=1)
    
    # Update existing question  
    question.put(question_id=135801)
    
    # Download from Metabase
    info = Question.get(135801, Path("questions/"))
"""

import json
import re
import logging
import urllib.error
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

from .utils import (
    get_metabase_config,
    get_state_dir,
    api_request,
    slugify,
    convert_colors_in_dict
)

# Configure logger (level set to INFO by default, DEBUG with --debug flag in main())
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# =============================================================================
# YAML/JSON Conversion Utilities
# =============================================================================

def yaml_to_json_question(question_yaml: Dict[str, Any], yaml_path: Path, database_id: int) -> Dict[str, Any]:
    """
    Convert YAML question definition to Metabase JSON format.
    
    Args:
        question_yaml: Parsed YAML question data
        yaml_path: Path to YAML file (for resolving SQL file references)
        database_id: Metabase database ID (deployment detail, not in YAML)
    
    Returns:
        Question definition in Metabase JSON format
    
    Raises:
        ValueError: If conversion fails or SQL file is invalid
    """
    # Handle SQL input (must be a file path)
    sql = question_yaml['sql']
    if not isinstance(sql, str):
        raise ValueError(f"Invalid SQL field type: {type(sql)}. Must be a string (file path).")
    
    # SQL must be a file reference
    if not sql.endswith('.sql'):
        raise ValueError(
            f"SQL must reference a .sql file, got: {sql}\n"
            f"Expected format: question.sql: 'path/to/query.sql'"
        )
    
    # Resolve SQL file path
    sql_path = yaml_path.parent / sql
    if not sql_path.exists():
        raise ValueError(f"SQL file not found: {sql}\nExpected at: {sql_path}")
    
    # Read SQL from file
    sql_query = sql_path.read_text()
    
    # Extract template tags from SQL query
    # Template variables use {{variable_name}}, INCLUDE directives use {{#card-id-alias}}
    template_tags = {}
    
    # Extract regular template variables ({{variable_name}})
    var_pattern = r'\{\{([^#}][^}]*)\}\}'
    var_matches = re.findall(var_pattern, sql_query)
    
    for variable_name in set(var_matches):
        variable_name = variable_name.strip()
        tag_id = str(uuid.uuid4())
        display_name = ' '.join(word.capitalize() for word in variable_name.split('_'))
        
        template_tags[variable_name] = {
            "id": tag_id,
            "name": variable_name,
            "display-name": display_name,
            "type": "text"
        }
    
    # Extract INCLUDE directives ({{#card-id-alias}})
    include_pattern = r'\{\{#(\d+)-([^}]+)\}\}'
    include_matches = re.findall(include_pattern, sql_query)

    for card_id_str, alias in include_matches:
        card_id = int(card_id_str)
        full_name = f"#{card_id_str}-{alias}"
        tag_id = str(uuid.uuid4())

        template_tags[full_name] = {
            "id": tag_id,
            "name": full_name,
            "display-name": full_name,
            "type": "card",
            "card-id": card_id
        }

    # Merge YAML parameter overrides into extracted template tags
    # Supports: type, display_name, default, required
    parameters = question_yaml.get('parameters', {})
    if parameters:
        for param_name, param_config in parameters.items():
            if param_name in template_tags:
                tag = template_tags[param_name]
                if 'type' in param_config:
                    # Map Metabase filter widget types to template-tag types
                    param_type = param_config['type']
                    if param_type.startswith('number'):
                        tag['type'] = 'number'
                    elif param_type.startswith('date'):
                        tag['type'] = 'date'
                    else:
                        tag['type'] = 'text'
                if 'display_name' in param_config:
                    tag['display-name'] = param_config['display_name']
                if 'default' in param_config:
                    tag['default'] = param_config['default']
                if param_config.get('required'):
                    tag['required'] = True

    # Build base question structure
    question_json = {
        "name": question_yaml['name'],
        "description": question_yaml.get('description'),
        "display": question_yaml['display'],
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {
                "query": sql_query,
                "template-tags": template_tags
            }
        },
        "visualization_settings": {}
    }
    
    # Convert visualization settings if present
    # Handles: column_settings (["name", "KEY"] format), graph.tooltip_columns, colors (to hex)
    if 'visualization_settings' in question_yaml:
        viz_yaml = question_yaml['visualization_settings']
        viz_json = {}
        
        for key, value in viz_yaml.items():
            if key == 'column_settings' and isinstance(value, dict):
                # Convert column_settings from simple keys to ["name", "KEY"] format
                converted = {}
                for col_name, col_settings in value.items():
                    json_key = json.dumps(["name", col_name])
                    converted_settings = convert_colors_in_dict(col_settings, direction='to_hex')
                    converted[json_key] = converted_settings
                viz_json[key] = converted
            elif key == 'graph.tooltip_columns' and isinstance(value, list):
                # Convert tooltip columns from simple strings to ["name", "KEY"] format
                converted = []
                for col_name in value:
                    converted.append(["name", col_name])
                viz_json[key] = converted
            elif key == 'series_settings' and isinstance(value, dict):
                viz_json[key] = convert_colors_in_dict(value, direction='to_hex')
            elif isinstance(value, dict):
                viz_json[key] = convert_colors_in_dict(value, direction='to_hex')
            else:
                viz_json[key] = value
        
        question_json['visualization_settings'] = viz_json
    
    return question_json


def json_to_yaml_question(question_json: Dict[str, Any], metabase_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert Metabase JSON question format to YAML ORM format.
    
    Converts hex color codes to palette names where possible and
    deserializes complex keys in visualization settings.
    
    Args:
        question_json: Question data from Metabase API
        metabase_url: Metabase instance URL (optional, for generating question URL)
    
    Returns:
        Question data in YAML ORM format
    """
    question_id = question_json.get("id")
    
    # Build question dict with url right after id
    question_dict = {"id": question_id}
    
    # Add URL if metabase_url is provided
    if metabase_url and question_id:
        question_dict["url"] = f"{metabase_url}/question/{question_id}"
    
    # Add remaining core fields
    question_dict["name"] = question_json.get("name")
    question_dict["display"] = question_json.get("display")
    # Note: database_id is NOT included (it's a deployment detail, stored in state file)
    
    question_yaml = {
        "question": question_dict
    }
    
    # Add optional fields if present
    if question_json.get("description"):
        question_yaml["question"]["description"] = question_json["description"]
    
    if question_json.get("collection_id"):
        question_yaml["question"]["collection_id"] = question_json["collection_id"]
    
    # Extract SQL from dataset_query (support both old and new MLv2 format)
    dataset_query = question_json.get("dataset_query", {})
    sql_query = None
    
    # Try new MLv2 format first: dataset_query.stages[0].native
    if "stages" in dataset_query and isinstance(dataset_query["stages"], list) and len(dataset_query["stages"]) > 0:
        stage = dataset_query["stages"][0]
        if "native" in stage:
            sql_query = stage["native"]
    
    # Fallback to old format: dataset_query.native.query
    if not sql_query and dataset_query.get("native"):
        sql_query = dataset_query["native"].get("query", "")
    
    # Add SQL to YAML if found
    if sql_query:
        question_yaml["question"]["sql"] = sql_query
    
    # Convert visualization settings if present
    # Handles: column_settings (simple keys), graph.tooltip_columns (simple strings), colors (to palette names)
    if question_json.get("visualization_settings"):
        viz_json = question_json["visualization_settings"]
    viz_yaml = {}
    
    for key, value in viz_json.items():
        if key == 'column_settings' and isinstance(value, dict):
            # Convert column_settings from ["name", "KEY"] format to simple keys
            converted = {}
            for col_key, col_settings in value.items():
                # Try to parse JSON array format: '["name","COLUMN_NAME"]'
                try:
                    parsed = json.loads(col_key)
                    if isinstance(parsed, list) and len(parsed) == 2 and parsed[0] == "name":
                        simple_key = parsed[1]
                    else:
                        simple_key = col_key  # Keep as-is if not expected format
                except (json.JSONDecodeError, TypeError):
                    simple_key = col_key  # Keep as-is if not JSON
                
                converted_settings = convert_colors_in_dict(col_settings, direction='to_name')
                converted[simple_key] = converted_settings
            viz_yaml[key] = converted
        elif key == 'graph.tooltip_columns' and isinstance(value, list):
            # Convert tooltip columns from ["name", "KEY"] format to simple strings
            converted = []
            for item in value:
                if isinstance(item, list) and len(item) == 2 and item[0] == "name":
                    converted.append(item[1])
                elif isinstance(item, str):
                    # Try to parse if it's a JSON string
                    try:
                        parsed = json.loads(item)
                        if isinstance(parsed, list) and len(parsed) == 2 and parsed[0] == "name":
                            converted.append(parsed[1])
                        else:
                            converted.append(item)
                    except (json.JSONDecodeError, TypeError):
                        converted.append(item)
                else:
                    converted.append(item)  # Keep as-is if not expected format
            viz_yaml[key] = converted
        elif isinstance(value, dict):
            viz_yaml[key] = convert_colors_in_dict(value, direction='to_name')
        else:
            viz_yaml[key] = value
    
        question_yaml["question"]["visualization_settings"] = viz_yaml
    
    return question_yaml


# =============================================================================
# Question ORM Class
# =============================================================================

class Question:
    """
    ORM-like interface for Metabase questions with local file management.
    
    Provides a high-level API for creating, updating, and downloading questions.
    
    Example:
        # Create a new question
        question = Question(Path("questions/my-question.yaml"))
        question_id = question.post(collection_id=123)
        
        # Update existing question  
        question.put(question_id=135801)
        
        # Download from Metabase
        info = Question.get(135801, Path("questions/"))
        # Returns: {"id": 135801, "filename": "135801-my-question.yaml", "url": "..."}
    """
    
    def __init__(self, file_path: Path):
        """
        Initialize Question from a local YAML file.
        
        Args:
            file_path: Path to question YAML file
        """
        self.file_path = Path(file_path)
        self._content = None
    
    @property
    def content(self) -> Dict[str, Any]:
        """Lazy load question YAML content."""
        if self._content is None:
            if not self.file_path.exists():
                raise FileNotFoundError(f"Question file not found: {self.file_path}")
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self._content = yaml.safe_load(f)
        return self._content
    
    @property
    def name(self) -> str:
        """Question name from YAML content."""
        return self.content.get("question", {}).get("name", "Untitled Question")
    
    def post(self, collection_id: int, database_id: int, debug: bool = False) -> int:
        """
        Create question in Metabase.
        
        Args:
            collection_id: Parent collection ID
            database_id: Database ID (deployment detail)
            debug: Enable debug output
        
        Returns:
            Created question ID
        
        Raises:
            urllib.error.HTTPError: If API request fails
        """
        
        logger.debug(f"Creating question: {self.name} in collection {collection_id}")
        
        # Convert YAML to JSON
        question_yaml = self.content.get("question", {})
        question_json = yaml_to_json_question(question_yaml, self.file_path, database_id)
        question_json["collection_id"] = collection_id
        
        # POST to Metabase API
        config = get_metabase_config()
        url = f"{config['url']}/api/card"
        response = api_request(url, config['api_key'], method="POST", data=question_json)
        question_id = response["id"]
        
        logger.info(f"✅ Question {question_id} created: {config['url']}/question/{question_id}")
        
        return question_id
    
    def put(self, question_id: int, database_id: Optional[int] = None, collection_id: Optional[int] = None, debug: bool = False) -> Dict[str, Any]:
        """
        Update existing question in Metabase.
        
        Args:
            question_id: Question ID to update
            database_id: Database ID (optional - if not provided, fetches from existing question)
            collection_id: Optional collection ID to move the question to
            debug: Enable debug output
        
        Returns:
            Updated question data from Metabase
        
        Raises:
            ValueError: If database_id cannot be determined
            urllib.error.HTTPError: If API request fails
        """

        logger.debug(f"Updating question {question_id}: {self.name}")
        
        # Fetch current database_id if not provided
        config = get_metabase_config()
        if database_id is None:
            logger.debug(f"Fetching current database_id for question {question_id}")
            url = f"{config['url']}/api/card/{question_id}"
            existing_question = api_request(url, config['api_key'])
            database_id = existing_question.get("database_id")
            if database_id is None:
                raise ValueError(f"Could not determine database_id for question {question_id}")
            logger.debug(f"Using existing database_id: {database_id}")
        
        # Convert YAML to JSON
        question_yaml = self.content.get("question", {})
        question_json = yaml_to_json_question(question_yaml, self.file_path, database_id)
        
        # Set collection_id if provided (move question)
        if collection_id is not None:
            question_json["collection_id"] = collection_id
            logger.debug(f"Moving question to collection {collection_id}")
        
        # PUT to Metabase API
        url = f"{config['url']}/api/card/{question_id}"
        response = api_request(url, config['api_key'], method="PUT", data=question_json)
        
        logger.info(f"✅ Question {question_id} updated: {config['url']}/question/{question_id}")
        
        return response
    
    @classmethod
    def get(cls, question_id: int, output_dir: Path, debug: bool = False) -> Dict[str, Any]:
        """
        Download question from Metabase and save as YAML.
        
        Args:
            question_id: Question ID to download
            output_dir: Directory to save the question file
            debug: Enable debug output and save raw JSON
        
        Returns:
            Dict with question info: {"id": int, "filename": str, "url": str}
        
        Raises:
            urllib.error.HTTPError: If question not found or API error
        """
        config = get_metabase_config()
        
        # Fetch question from API
        url = f"{config['url']}/api/card/{question_id}"
        question_data = api_request(url, config['api_key'])
        question_name = question_data.get("name", f"Question {question_id}")
        
        logger.info(f"Downloading question {question_id}: {question_name}")
        
        # Create output directory
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename: {id}-{slug}.yaml
        slug = slugify(question_name)
        yaml_filename = f"{question_id}-{slug}.yaml"
        yaml_path = output_dir / yaml_filename
        
        # Convert to YAML format
        question_yaml = json_to_yaml_question(question_data)
        
        # Strip ID from question YAML (for Terraform-like workflow)
        if "question" in question_yaml and "id" in question_yaml["question"]:
            del question_yaml["question"]["id"]
        if "question" in question_yaml and "collection_id" in question_yaml["question"]:
            del question_yaml["question"]["collection_id"]
        
        # Extract SQL and write to separate file
        if "question" in question_yaml and "sql" in question_yaml["question"]:
            sql_content = question_yaml["question"]["sql"]
            if sql_content:  # Only write SQL file if there's actual content
                # Generate SQL filename: {id}-{slug}-query.sql
                sql_filename = f"{question_id}-{slug}-query.sql"
                sql_path = output_dir / sql_filename
            
                # Write SQL to file
                with open(sql_path, 'w', encoding='utf-8') as f:
                    f.write(sql_content)
            
                # Replace SQL content with file reference in YAML
                question_yaml["question"]["sql"] = sql_filename
                logger.debug(f"Saved SQL to {sql_filename}")
        
        # Save YAML file
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(question_yaml, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        logger.info(f"✅ Saved to {yaml_path}")
        
        # Save raw JSON if debug mode
        if debug:
            json_filename = f"{question_id}-{slug}.json"
            json_path = output_dir / json_filename
            with open(json_path, 'w') as f:
                json.dump(question_data, f, indent=2)
            logger.debug(f"Saved debug JSON: {json_path}")
        
        # Return info dict (includes database_id for state file)
        return {
            "id": question_id,
            "database_id": question_data.get("database_id"),
            "filename": yaml_filename,
            "url": f"{config['url']}/question/{question_id}"
        }

