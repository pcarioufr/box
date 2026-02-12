#!/Users/pierre.cariou/Code/onboarding-analytics/.venv/bin/python
"""
Metabase Dashboard Operations

Provides ORM-style interface for Metabase dashboards with local file management.

Example:
    # Pull dashboard from Metabase
    dashboard = Dashboard.pull(dashboard_id=123, directory=Path("my-dashboard/"))
    
    # Push dashboard to Metabase (create new)
    dashboard = Dashboard.push(directory=Path("my-dashboard/"), 
                               collection_id=456, 
                               database_id=1)
    
    # Push dashboard to Metabase (update existing)
    dashboard = Dashboard.push(directory=Path("my-dashboard/"))
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import urllib.error

from .utils import (
    get_metabase_config,
    get_state_dir,
    api_request,
    slugify,
    convert_colors_in_dict
)
from .collection import get_collection, post_collection

# Configure logger
logger = logging.getLogger(__name__)


# =============================================================================
# Dashboard ORM Class
# =============================================================================

class Dashboard:
    """
    ORM-style interface for Metabase dashboards.
    
    Metabase is the source of truth; YAML files are the editing interface.
    Use Dashboard.pull() to download or Dashboard.push() to upload.
    
    Usage:
        # Pull dashboard from Metabase
        dashboard = Dashboard.pull(123, directory="path/to/dir")
        
        # Push dashboard to Metabase
        dashboard = Dashboard.push("path/to/dir", collection_id=123, database_id=1)
    """
    
    # Hardcoded structure (standardized layout)
    DEFINITION_FILE = "dashboard.yaml"
    STATE_FILE = ".state.yaml"
    
    def __init__(self, directory: Path, _internal: bool = False):
        """
        Initialize Dashboard from a local directory.
        
        Note: This is an internal constructor. Use Dashboard.pull() or 
        Dashboard.push() instead.
        
        Args:
            directory: Path to dashboard directory
            _internal: Internal flag to prevent direct instantiation
        """
        if not _internal:
            logger.warning(
                "Direct Dashboard() instantiation is discouraged. "
                "Use Dashboard.pull() or Dashboard.push() instead."
            )
        
        self.dir = Path(directory)
        self._definition = None
        self._state = None
    
    @property
    def definition_yaml(self) -> Path:
        """Path to dashboard definition file (hardcoded as dashboard.yaml)."""
        return self.dir / self.DEFINITION_FILE
    
    @property
    def state_path(self) -> Path:
        """Path to state file (hardcoded as .state.yaml)."""
        return self.dir / self.STATE_FILE
    
    @property
    def definition(self) -> Dict[str, Any]:
        """
        Lazy load dashboard definition from YAML file.
        
        Note: This is read-only. To modify the definition, edit the YAML file directly.
        The YAML file is the source of truth for dashboard content.
        """
        if self._definition is None:
            if not self.definition_yaml or not self.definition_yaml.exists():
                raise FileNotFoundError(f"No dashboard YAML found in {self.dir}")
            
            import yaml
            with open(self.definition_yaml, 'r', encoding='utf-8') as f:
                self._definition = yaml.safe_load(f)
            
            # Validate structure
            if "dashboard" not in self._definition:
                raise ValueError(f"Invalid dashboard YAML: missing 'dashboard' key in {self.definition_yaml}")
            
            # Validate cards
            def validate_card(card: Dict[str, Any], location: str):
                """Validate a single card structure."""
                # Non-virtual cards must have question_file
                if "virtual_card" not in card and "question_file" not in card:
                    raise ValueError(
                        f"Invalid dashboard YAML: card {location} "
                        f"is missing 'question_file' (non-virtual cards must reference a question file)"
                    )
            
            dashboard = self._definition["dashboard"]
            
            # Check cards in tabs
            for tab_idx, tab in enumerate(dashboard.get("tabs", [])):
                tab_name = tab.get("name", f"tab {tab_idx}")
                for card_idx, card in enumerate(tab.get("cards", [])):
                    validate_card(card, f"{card_idx} in tab '{tab_name}'")
            
            # Check flat cards at dashboard level
            for card_idx, card in enumerate(dashboard.get("cards", [])):
                validate_card(card, f"{card_idx} at dashboard level")
        
        return self._definition
    
    @property
    def state(self) -> Optional[Dict[str, Any]]:
        """Lazy load state file if it exists."""
        if self._state is None and self.state_path.exists():
            import yaml
            with open(self.state_path, 'r', encoding='utf-8') as f:
                self._state = yaml.safe_load(f)
        return self._state
    
    @state.setter
    def state(self, state_data: Dict[str, Any]):
        """
        Save state to file and update cache.
        
        Note: State is programmatically managed during push/pull operations.
        It tracks synchronization metadata (IDs, timestamps, URLs).
        """
        import yaml
        with open(self.state_path, 'w', encoding='utf-8') as f:
            yaml.dump(state_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        self._state = state_data
    
    @property
    def remote_id(self) -> Optional[int]:
        """
        Dashboard ID in Metabase (from state file).
        
        Returns None if dashboard hasn't been synced to Metabase yet.
        """
        if self.state and "dashboard" in self.state:
            return self.state["dashboard"].get("id")
        return None
    
    @property
    def name(self) -> str:
        """Dashboard name from definition."""
        return self.definition.get("dashboard", {}).get("name", "Untitled Dashboard")
    
    @property
    def description(self) -> Optional[str]:
        """Dashboard description from definition."""
        return self.definition.get("dashboard", {}).get("description")
    
    def _find_question_files(self) -> List[Path]:
        """
        Find all question YAML files in dashboard directory.
        
        Excludes:
        - dashboard.yaml (DEFINITION_FILE)
        - .state.yaml (STATE_FILE)
        - Files in hidden directories (starting with '.')
        
        Returns:
            Sorted list of question YAML file paths
        """
        question_files = []
        for yaml_file in sorted(self.dir.rglob("*.yaml")):
            # Skip dashboard definition and state files
            if yaml_file.name in [self.DEFINITION_FILE, self.STATE_FILE]:
                continue
            # Skip hidden directories
            if any(part.startswith('.') for part in yaml_file.relative_to(self.dir).parts[:-1]):
                continue
            question_files.append(yaml_file)
        return question_files
    
    
    def _translate_question_files_to_ids(self, question_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate question_file references to card_id in dashboard content.
        
        Args:
            question_state: Question state mapping (id -> {file, url, ...})
        
        Returns:
            Modified dashboard content with card_id instead of question_file
        """
        dashboard_definition = self.definition.copy()
        dashboard = dashboard_definition["dashboard"]
        
        # Build reverse mapping: file -> id for O(1) lookup
        file_to_id = {}
        for qid, qinfo in question_state.items():
            if isinstance(qid, int) and qid > 0:  # Skip negative IDs (failed questions)
                file_to_id[qinfo["file"]] = qid
        
        # Helper to translate a single card
        def translate_card(card):
            if "question_file" in card:
                question_file = card["question_file"]
                
                # Look up question ID in reverse mapping
                if question_file not in file_to_id:
                    raise ValueError(f"Question file not found in state: {question_file}")
                
                question_id = file_to_id[question_file]
                
                # Replace question_file with card_id
                if "card" not in card:
                    card["card"] = {}
                card["card"]["question_id"] = question_id
                del card["question_file"]
        
        # Process cards in tabs
        for tab in dashboard.get("tabs", []):
            for card in tab.get("cards", []):
                translate_card(card)
        
        # Process flat cards at dashboard level (when no tabs)
        for card in dashboard.get("cards", []):
            translate_card(card)
        
        return dashboard_definition

    def _create_questions_with_state(
        self,
        collection_id: int,
        database_id: int,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Create all questions in directory and return state mapping.
        
        Args:
            collection_id: Metabase collection ID for questions
            database_id: Database ID for questions (deployment detail)
            debug: Enable debug output
        
        Returns:
            Dict mapping question file paths (relative to dashboard_dir) to state info
        """
        from .question import Question
        
        state = {}
        created_count = 0
        failed_count = 0
        
        # Find all question YAML files
        question_files = self._find_question_files()
        
        if not question_files:
            logger.warning(f"No question YAML files found in {self.dir}")
            return state
        
        for question_file in question_files:
            # Calculate relative path from dashboard directory
            rel_path = question_file.relative_to(self.dir)
            rel_path_str = str(rel_path)
            
            try:
                # Create question using Question class
                question = Question(question_file)
                new_question_id = question.post(
                    collection_id=collection_id,
                    database_id=database_id,
                    debug=False
                )
                
                # Get config for URL (for logging only)
                config = get_metabase_config()
                metabase_url = config["url"].rstrip("/")
                
                # Record success in state with ID as primary key
                state[new_question_id] = {
                    "file": rel_path_str
                }
                
                created_count += 1
                logger.info(f"Created question {new_question_id}: {rel_path_str} ({metabase_url}/question/{new_question_id})")
            
            except Exception as e:
                # Record failure in state with ID as key (use negative placeholder)
                # Generate a temporary negative ID for failed questions
                failed_id = -(failed_count + 1)
                state[failed_id] = {
                    "file": rel_path_str,
                    "status": "failed",
                    "error": str(e)
                }
                failed_count += 1
                logger.error(f"Failed to create {rel_path_str}: {e}")
        
        # Log summary
        if failed_count > 0:
            logger.warning(f"Created {created_count}/{len(question_files)} questions ({failed_count} failed)")
        else:
            logger.info(f"Created {created_count} questions")
        
        return state


    def _update_questions_with_state(
        self,
        existing_state: Dict[int, Any],
        database_id: int,
        debug: bool = False
    ) -> Dict[int, Any]:
        """
        Update existing questions from local files.
        
        Args:
            existing_state: Current question state (ID -> {file})
            database_id: Database ID for questions (deployment detail)
            debug: Enable debug output
        
        Returns:
            Updated state mapping (same structure as input)
        """
        from .question import Question
        
        updated_count = 0
        failed_count = 0
        
        # Build a reverse map: file -> question_id
        file_to_id = {}
        for question_id, info in existing_state.items():
            if isinstance(question_id, int) and question_id > 0:
                file_path = info.get("file")
                if file_path:
                    file_to_id[file_path] = question_id
        
        # Find all question YAML files
        question_files = self._find_question_files()
        
        if not question_files:
            logger.warning(f"No question YAML files found in {self.dir}")
            return existing_state
        
        # Update each question
        for question_file in question_files:
            rel_path = question_file.relative_to(self.dir)
            rel_path_str = str(rel_path)
            
            # Get the existing question ID for this file
            question_id = file_to_id.get(rel_path_str)
            
            if not question_id:
                logger.warning(f"No existing ID found for {rel_path_str}, skipping update")
                continue
            
            try:
                # Update question using Question class
                question = Question(question_file)
                question.put(
                    question_id=question_id,
                    database_id=database_id,
                    debug=False
                )
                
                updated_count += 1
                logger.info(f"Updated question {question_id}: {rel_path_str}")
            
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to update {rel_path_str} (ID {question_id}): {e}")
        
        # Log summary
        if failed_count > 0:
            logger.warning(f"Updated {updated_count}/{len(question_files)} questions ({failed_count} failed)")
        else:
            logger.info(f"Updated {updated_count} questions")
        
        # Return the same state (IDs don't change on update)
        return existing_state



    @classmethod
    def _to_json(cls, yaml_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert dashboard YAML format to Metabase JSON format.
    
        Args:
            yaml_def: Dashboard definition in YAML format
    
        Returns:
            Dashboard in Metabase JSON format
        """
        
        def _yaml_card_to_dashcard(card: Dict[str, Any], tab_id: Optional[int], dashcard_id: int) -> Dict[str, Any]:

            """Convert a single YAML card to Metabase dashcard format."""
            # Validate card structure
            if "position" not in card:
                raise ValueError(
                    "Card missing required 'position' object.\n"
                    "See libs/metabase/model.md > 'Card Placement Format' for structure details."
                )
                    
            position = card["position"]
            required_pos_fields = ["row", "col", "size_x", "size_y"]
            missing_fields = [f for f in required_pos_fields if f not in position]
            
            if missing_fields:
                missing_str = ", ".join(missing_fields)
                raise ValueError(
                    f"Card position missing required fields: {missing_str}\n"
                    "See libs/metabase/model.md > 'Card Placement Format' for details."
                )
                    
            has_card_id = "card_id" in card
            has_card = "card" in card
            has_virtual_card = "virtual_card" in card
            
            if not (has_card_id or has_card or has_virtual_card):
                raise ValueError(
                    "Card must have either 'card_id' (for question cards) or 'virtual_card' (for text/heading cards).\n"
                    "See libs/metabase/model.md > 'Card Placement Format' for examples."
                )
            
            if (has_card_id or has_card) and has_virtual_card:
                raise ValueError(
                    "Card cannot have both 'card_id' and 'virtual_card'.\n"
                    "See libs/metabase/model.md > 'Card Placement Format' for details."
                )
                    
            # Build dashcard
            dashcard = {
                "id": dashcard_id,
                "row": position["row"],
                "col": position["col"],
                "size_x": position["size_x"],
                "size_y": position["size_y"]
            }
            
            if tab_id is not None:
                dashcard["dashboard_tab_id"] = tab_id
            
            # Regular card with card_id (direct reference)
            if "card_id" in card:
                dashcard["card_id"] = card["card_id"]
            
            # Regular card with nested card.question_id (legacy format)
            elif "card" in card:
                dashcard["card_id"] = card["card"]["question_id"]
            
            # Virtual card
            elif "virtual_card" in card:
                vcard = card["virtual_card"]
                dashcard["visualization_settings"] = {
                    "virtual_card": {
                        "name": None,
                        "dataset_query": {},
                        "display": vcard.get("display", "text"),
                        "visualization_settings": {},
                        "archived": False
                    }
                }
        
                
                if "text" in vcard:
                    dashcard["visualization_settings"]["text"] = vcard["text"]
                
                # Handle text alignment
                if "text_align" in vcard:
                    text_align = vcard["text_align"]
                    if text_align == "center":
                        dashcard["visualization_settings"]["text.align_horizontal"] = "center"
                    elif text_align == "right":
                        dashcard["visualization_settings"]["text.align_horizontal"] = "right"
                    # left is default, no need to set
            # Parameter mappings
            if "parameter_mappings" in card:
                dashcard["parameter_mappings"] = []
                for mapping in card["parameter_mappings"]:
                    converted_mapping = {
                        "parameter_id": mapping["parameter_id"]
                    }

                    # Metabase requires card_id inside each parameter mapping
                    if dashcard.get("card_id"):
                        converted_mapping["card_id"] = dashcard["card_id"]

                    # Convert simplified target format to Metabase format
                    target = mapping.get("target")
                    if isinstance(target, str):
                        # Simple string format: "signup_type"
                        # Convert to: ["variable", ["template-tag", "signup_type"]]
                        converted_mapping["target"] = ["variable", ["template-tag", target]]
                    else:
                        # Already in complex format, use as-is
                        converted_mapping["target"] = target

                    dashcard["parameter_mappings"].append(converted_mapping)
            
            return dashcard
    
        dashboard = yaml_def.get("dashboard", {})
        json_def = {}
        
        # Simple fields that map directly
        if "width" in dashboard:
            json_def["width"] = dashboard["width"]
        
        if "parameters" in dashboard:
            json_def["parameters"] = dashboard["parameters"]
        
        # Convert tabs and cards to flat dashcards array
        dashcards = []
        tabs = dashboard.get("tabs", [])
        
        # Prepare tabs for Metabase
        if tabs:
            json_def["tabs"] = []
            for tab in tabs:
                tab_data = {
                    "id": -(tab.get("position", 0) + 1),  # Use position to generate ID
                    "name": tab["name"],
                    "position": tab["position"]
                }
                json_def["tabs"].append(tab_data)
        
        # Process cards from tabs
        for tab_index, tab in enumerate(tabs):
            tab_id = -(tab.get("position", 0) + 1)  # Same ID generation as above
            cards = tab.get("cards", [])
            
            for card_index, card in enumerate(cards):
                dashcard_id = -(len(dashcards) + 1)
                dashcard = _yaml_card_to_dashcard(card, tab_id, dashcard_id)
                dashcards.append(dashcard)
        
        # If no tabs, check for cards at dashboard level
        if not tabs:
            for card_index, card in enumerate(dashboard.get("cards", [])):
                dashcard_id = -(card_index + 1)
                dashcard = _yaml_card_to_dashcard(card, None, dashcard_id)
                dashcards.append(dashcard)
        
        json_def["dashcards"] = dashcards
        
        # Validate json_def structure
        dashcards_with_tabs = [dc for dc in json_def.get("dashcards", []) if dc.get("dashboard_tab_id") is not None]
        if dashcards_with_tabs and "tabs" not in json_def:
            raise ValueError(
                f"Dashboard has {len(dashcards_with_tabs)} dashcards with tab references "
                f"but 'tabs' field is missing. Please include tabs in the definition file."
            )
        
        return json_def
    
    
    @classmethod
    def _from_json(cls, json_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Metabase JSON dashboard format to YAML format.
        
        Args:
            json_def: Dashboard definition from Metabase API (JSON format)
        
        Returns:
            Dashboard definition in YAML format
        """
        yaml_def = {
        "dashboard": {
                "id": json_def.get("id"),
                "name": json_def.get("name"),
                "width": json_def.get("width", "full"),
        }
    }
    
    # Add optional fields if present
        if json_def.get("description"):
            yaml_def["dashboard"]["description"] = json_def["description"]
        
        if json_def.get("collection_id"):
            yaml_def["dashboard"]["collection_id"] = json_def["collection_id"]
        
        # Process tabs (under dashboard)
        tabs = json_def.get("tabs", [])
        if tabs:
            yaml_def["dashboard"]["tabs"] = []
            for tab in sorted(tabs, key=lambda t: t.get("position", 0)):
                tab_yaml = {
                    "id": tab.get("id"),
                    "name": tab.get("name"),
                    "position": tab.get("position", 0)
                }
                yaml_def["dashboard"]["tabs"].append(tab_yaml)
        
        # Process parameters (under dashboard)
        parameters = json_def.get("parameters", [])
        if parameters:
            yaml_def["dashboard"]["parameters"] = []
            for param in parameters:
                param_yaml = {
                "id": param.get("id"),
                "name": param.get("name"),
                    "slug": param.get("slug"),
                    "type": param.get("type")
                }
                if param.get("default"):
                    param_yaml["default"] = param["default"]
                if param.get("values_source_type"):
                    param_yaml["values_source_type"] = param["values_source_type"]
                if param.get("values_source_config"):
                    param_yaml["values_source_config"] = param["values_source_config"]
                if param.get("required"):
                    param_yaml["required"] = param["required"]
                yaml_def["dashboard"]["parameters"].append(param_yaml)
        
        # Process dashcards - organize by tab or under dashboard if no tabs
        dashcards = json_def.get("dashcards", [])
        if dashcards:
            # Build card YAML objects
            card_yamls = []
            for dashcard in sorted(dashcards, key=lambda c: c.get("row", 0)):
                card = dashcard.get("card", {})
                
                # Build position object (required in YAML format)
                card_yaml = {
                    "position": {
                        "row": dashcard.get("row", 0),
                        "col": dashcard.get("col", 0),
                        "size_x": dashcard.get("size_x", 4),
                        "size_y": dashcard.get("size_y", 4)
                    }
                }
                
                # Add card_id for regular cards, or virtual_card for text/heading cards
                if isinstance(card, dict) and card.get("id"):
                    card_yaml["card_id"] = card.get("id")
                
                # Check for virtual card in visualization_settings
                vis_settings = dashcard.get("visualization_settings", {})
                if "virtual_card" in vis_settings:
                    vcard_data = vis_settings["virtual_card"]
                    card_yaml["virtual_card"] = {
                        "display": vcard_data.get("display", "text")
                    }
                    
                    # Extract text from visualization_settings (it's at the top level)
                    if "text" in vis_settings:
                        card_yaml["virtual_card"]["text"] = vis_settings["text"]
                    
                    # Extract text alignment
                    text_align = vis_settings.get("text.align_horizontal")
                    if text_align == "center":
                        card_yaml["virtual_card"]["text_align"] = "center"
                    elif text_align == "right":
                        card_yaml["virtual_card"]["text_align"] = "right"
                    # left is default, no need to include
                
                # Tab reference (temporary, will be removed when organizing by tab)
                if dashcard.get("dashboard_tab_id"):
                    card_yaml["dashboard_tab_id"] = dashcard["dashboard_tab_id"]
                
                # Series
                if dashcard.get("series"):
                    card_yaml["series"] = [s.get("id") for s in dashcard["series"] if isinstance(s, dict) and s.get("id")]
                
                # Parameter mappings
                if dashcard.get("parameter_mappings"):
                    card_yaml["parameter_mappings"] = []
                    for pm in dashcard["parameter_mappings"]:
                        pm_yaml = {
                            "parameter_id": pm.get("parameter_id")
                        }
                        
                        # Simplify target format if it's a template variable
                        target = pm.get("target")
                        if isinstance(target, list) and len(target) == 2:
                            if target[0] == "variable" and isinstance(target[1], list) and len(target[1]) == 2:
                                if target[1][0] == "template-tag":
                                    # Simplify: ["variable", ["template-tag", "name"]] -> "name"
                                    pm_yaml["target"] = target[1][1]
                                else:
                                    pm_yaml["target"] = target
                            else:
                                pm_yaml["target"] = target
                        else:
                            pm_yaml["target"] = target
                        
                        card_yaml["parameter_mappings"].append(pm_yaml)
                
                card_yamls.append(card_yaml)
            
            # Organize cards by tab if tabs exist
            if "tabs" in yaml_def.get("dashboard", {}):
                # Group cards by tab_id
                for tab in yaml_def["dashboard"]["tabs"]:
                    tab_id = tab["id"]
                    tab_cards = [c for c in card_yamls if c.get("dashboard_tab_id") == tab_id]
                    # Remove dashboard_tab_id from cards (redundant in this structure)
                    for card in tab_cards:
                        if "dashboard_tab_id" in card:
                            del card["dashboard_tab_id"]
                    tab["cards"] = tab_cards
            else:
                # No tabs - put cards at dashboard level
                yaml_def["dashboard"]["cards"] = card_yamls
        
        return yaml_def


    @classmethod
    def pull(cls, dashboard_id: int, directory: Path, debug: bool = False) -> "Dashboard":
        """
        Pull dashboard from Metabase and save/update locally.
        
        Downloads the dashboard definition and all its questions to the specified directory.
        Creates the directory if it doesn't exist; overwrites if it does.
        
        Args:
            dashboard_id: Metabase dashboard ID to pull
            directory: Target directory for dashboard (will be created if missing)
            debug: Enable debug output and save raw JSON
        
        Returns:
            Dashboard instance
            
        Example:
            dashboard = Dashboard.pull(123, Path("my-dashboard/"))
            # Creates:
            #   my-dashboard/dashboard.yaml
            #   my-dashboard/.state.yaml
            #   my-dashboard/*.yaml (questions, flat if no tabs)
            #   my-dashboard/01-tab-name/*.yaml (questions in tab subdirs if tabs exist)
        
        Raises:
            urllib.error.HTTPError: If dashboard not found or API error
        """
        config = get_metabase_config()
        
        # Fetch dashboard from API
        url = f"{config['url']}/api/dashboard/{dashboard_id}"
        dashboard_data = api_request(url, config['api_key'])
        dashboard_name = dashboard_data.get("name", f"Dashboard {dashboard_id}")
        
        logger.info(f"Pulling dashboard {dashboard_id}: {dashboard_name}")
        
        # Create directory (no confirmation needed)
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        
        # Convert to YAML format
        yaml_def = cls._from_json(dashboard_data)
        
        # Strip runtime/deployment fields from dashboard definition (keep only in .state.yaml)
        # These fields are deployment-specific and should not be in the source files
        if "dashboard" in yaml_def:
            # Remove ID (tracked in state)
            if "id" in yaml_def["dashboard"]:
                del yaml_def["dashboard"]["id"]
            # Remove collection_id (tracked in state, specified via --parent flag)
            if "collection_id" in yaml_def["dashboard"]:
                del yaml_def["dashboard"]["collection_id"]
        
        # Save definition to hardcoded filename
        definition_path = directory / cls.DEFINITION_FILE
        import yaml
        with open(definition_path, 'w') as f:
            yaml.dump(yaml_def, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=1000)
        
        # Save raw JSON if debug mode
        if debug:
            json_path = directory / "dashboard-debug.json"
            with open(json_path, 'w') as f:
                json.dump(dashboard_data, f, indent=2)
        
        # Download questions
        questions_info = {}
        from .question import Question
        
        # Build tab_id -> folder map if tabs exist
        tab_id_to_folder = {}
        tabs = dashboard_data.get("tabs", [])
        
        if tabs:
            # Sort tabs by position and create subdirectories directly under dashboard directory
            sorted_tabs = sorted(tabs, key=lambda t: t.get("position", 0))
            
            for tab_index, tab in enumerate(sorted_tabs, 1):
                tab_name = tab.get("name", f"Tab {tab_index}")
                tab_id = tab.get("id")
                
                # Create folder name: {rank:02d}-{slug}
                tab_slug = slugify(tab_name)
                tab_folder = f"{tab_index:02d}-{tab_slug}"
                tab_dir = directory / tab_folder
                tab_dir.mkdir(parents=True, exist_ok=True)
                
                tab_id_to_folder[tab_id] = tab_folder
        
        # Download questions directly from dashcards
        total_cards = len(dashboard_data.get("dashcards", []))
        first_database_id = None  # Track database_id from first question
        
        if total_cards > 0:
            logger.info(f"Downloading questions from {total_cards} cards...")
        
        for dashcard in dashboard_data.get("dashcards", []):
            card = dashcard.get("card")
            if not card or not isinstance(card, dict):
                continue
            
            card_id = card.get("id")
            if not card_id:
                continue
            
            try:
                # Determine target directory based on tab
                dashboard_tab_id = dashcard.get("dashboard_tab_id")
                if dashboard_tab_id and dashboard_tab_id in tab_id_to_folder:
                    # Place in tab subdirectory directly under dashboard directory
                    tab_folder = tab_id_to_folder[dashboard_tab_id]
                    target_dir = directory / tab_folder
                    rel_path_prefix = tab_folder
                else:
                    # No tab or tab not found - place flat in dashboard directory
                    tab_folder = None
                    target_dir = directory
                    rel_path_prefix = ""
                
                # Download question as YAML
                question_info = Question.get(card_id, target_dir, debug=debug)
                if question_info:
                    if rel_path_prefix:
                        rel_path = f"{rel_path_prefix}/{question_info['filename']}"
                    else:
                        rel_path = question_info['filename']
                    # Use ID as primary key, store file only
                    questions_info[card_id] = {
                        "file": rel_path
                    }
                    
                    # Store first database_id we see (all questions use same database)
                    if first_database_id is None and question_info.get("database_id"):
                        first_database_id = question_info.get("database_id")

            except Exception as e:
                logger.warning(f"Question {card_id} failed: {e}")
        
        # Create Dashboard instance and set state
        dashboard = cls(directory, _internal=True)
        sync_timestamp = datetime.utcnow().isoformat() + "Z"
        
        dashboard.state = {
            "meta": {
                "last_synced": sync_timestamp,
                "database_id": first_database_id  # Store database_id once in meta
            },
            "dashboard": {
                "file": cls.DEFINITION_FILE,
                "id": dashboard_id,
                "collection_id": dashboard_data.get("collection_id"),
                "url": f"{config['url']}/dashboard/{dashboard_id}"
            },
            "questions": questions_info
        }
        
        logger.info(f"✅ Saved to {directory}/ with {len(questions_info)} questions")
        
        return dashboard

    @classmethod
    def push(cls, directory: Path, collection_id: Optional[int] = None, 
             database_id: Optional[int] = None, debug: bool = False) -> "Dashboard":
        """
        Push dashboard from local directory to Metabase (create or update).
        
        Automatically detects whether to create or update based on .state.yaml:
        - If .state.yaml exists → update existing dashboard
        - If .state.yaml missing → create new dashboard (requires collection_id & database_id)
        
        When creating a new dashboard, automatically creates a sub-collection named after
        the dashboard within the specified parent collection.
        
        Args:
            directory: Path to dashboard directory (must exist)
            collection_id: Parent collection ID where dashboard collection will be created (required for new dashboards)
            database_id: Database ID for questions (required for new dashboards)
            debug: Enable debug output
        
        Returns:
            Dashboard instance
            
        Example:
            # Create new dashboard (auto-creates "My Dashboard" collection in parent 123)
            dashboard = Dashboard.push("my-dashboard/", 
                                      collection_id=123,  # parent collection
                                      database_id=1)
            
            # Update existing dashboard
            dashboard = Dashboard.push("my-dashboard/")
        
        Raises:
            ValueError: If directory doesn't exist or collection_id/database_id missing for new dashboard
            FileNotFoundError: If dashboard.yaml not found in directory
        """
        directory = Path(directory)
        
        # Check directory exists
        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")
        
        dashboard = cls(directory, _internal=True)
        
        # Check if dashboard exists remotely
        if not dashboard.remote_id:
            # Create new dashboard
            if collection_id is None or database_id is None:
                raise ValueError(
                    "collection_id and database_id are required when creating a new dashboard.\n"
                    f"Usage: Dashboard.push('{directory}', collection_id=123, database_id=1)"
                )
            
            # Auto-create collection if needed
            # Use dashboard name as collection name
            collection_name = dashboard.name
            config = get_metabase_config()
            
            # Try to find existing collection with this name in parent
            parent_url = f"{config['url']}/api/collection/{collection_id}"
            try:
                parent_info = api_request(parent_url, config['api_key'], method="GET")
                # Collection exists, we'll use it as parent
                logger.info(f"Using parent collection: {collection_id}")
            except Exception:
                # Parent doesn't exist or we don't have access
                raise ValueError(
                    f"Parent collection {collection_id} not found or not accessible.\n"
                    "Please verify the collection ID and your permissions."
                )
            
            # Create a sub-collection for this dashboard
            logger.info(f"Creating collection '{collection_name}' in parent collection {collection_id}")
            
            try:
                new_collection = post_collection(
                    name=collection_name,
                    parent_id=collection_id,
                    description=f"Auto-created for dashboard: {dashboard.name}"
                )
                actual_collection_id = new_collection["id"]
                logger.info(f"✅ Created collection {actual_collection_id}: {collection_name}")
            except Exception as e:
                logger.error(f"Failed to create collection: {e}")
                raise ValueError(
                    f"Could not create collection '{collection_name}' in parent {collection_id}: {e}\n"
                    "Please create the collection manually or check your permissions."
                )
            
            logger.info(f"Creating new dashboard: {dashboard.name}")
            
            # POST empty dashboard shell to get an ID (in the new sub-collection)
            url = f"{config['url']}/api/dashboard"
            dashboard_data = {
                "name": dashboard.name,
                "collection_id": actual_collection_id,  # Use the auto-created collection
            }
            if dashboard.description:
                dashboard_data["description"] = dashboard.description
            
            result = api_request(url, config['api_key'], method="POST", data=dashboard_data)
            dashboard_id = result["id"]
            
            # Initialize state with the new ID
            metabase_url = config["url"].rstrip("/")
            sync_timestamp = datetime.utcnow().isoformat() + "Z"
            
            dashboard.state = {
                "meta": {
                    "last_synced": sync_timestamp,
                    "database_id": database_id,  # Store database_id in meta
                    "parent_collection_id": collection_id  # Track parent for reference
                },
                "dashboard": {
                    "file": dashboard.definition_yaml.name,
                    "id": dashboard_id,
                    "collection_id": actual_collection_id  # The auto-created collection
                },
                "questions": {}
            }
            
            logger.info(f"Created empty dashboard {dashboard_id} ({metabase_url}/dashboard/{dashboard_id})")
            logger.info(f"Dashboard is in collection {actual_collection_id}")
        else:
            logger.info(f"Updating dashboard {dashboard.remote_id}: {dashboard.name}")
            dashboard_id = dashboard.remote_id
            # Use collection_id from state (the auto-created collection, not parent)
            actual_collection_id = dashboard.state["dashboard"].get("collection_id")
            # Read database_id from meta
            database_id = dashboard.state.get("meta", {}).get("database_id")
            if database_id is None:
                raise ValueError(
                    f"database_id not found in state file. "
                    f"The state file may be corrupted or from an incompatible version."
                )
        
        # Create/update questions if needed (use actual_collection_id, not parent collection_id)
        if actual_collection_id and database_id:
            # Find question files
            question_files = dashboard._find_question_files()
            
            if question_files:
                # Check if this is create or update mode
                existing_questions = dashboard.state.get("questions", {}) if dashboard.state else {}
                
                if not existing_questions:
                    # Create mode: no existing questions
                    logger.info(f"Creating {len(question_files)} questions")
                    question_state = dashboard._create_questions_with_state(actual_collection_id, database_id, debug)
                else:
                    # Update mode: questions already exist, update them
                    logger.info(f"Updating {len(existing_questions)} questions")
                    question_state = dashboard._update_questions_with_state(existing_questions, database_id, debug)
                
                # Update state with question info and sync timestamp
                sync_timestamp = datetime.utcnow().isoformat() + "Z"
                if "meta" not in dashboard.state:
                    dashboard.state["meta"] = {}
                dashboard.state["meta"]["last_synced"] = sync_timestamp
                dashboard.state["meta"]["database_id"] = database_id  # Store database_id in meta
                dashboard.state["questions"] = question_state
                
                # Save updated state
                import yaml
                with open(dashboard.state_path, 'w', encoding='utf-8') as f:
                    yaml.dump(dashboard.state, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                
                # Translate question_file references to card_id
                if question_state:
                    definition_with_ids = dashboard._translate_question_files_to_ids(question_state)
                else:
                    definition_with_ids = dashboard.definition
            else:
                definition_with_ids = dashboard.definition
        else:
            definition_with_ids = dashboard.definition
        
        # Convert YAML to JSON
        json_def = cls._to_json(definition_with_ids)
        
        if debug:
            # Save JSON representation next to YAML file
            json_filename = dashboard.definition_yaml.stem + "-debug.json"
            json_path = dashboard.definition_yaml.parent / json_filename
            with open(json_path, 'w') as f:
                json.dump(json_def, f, indent=2)
        
        # PUT to Metabase API
        config = get_metabase_config()
        url = f"{config['url']}/api/dashboard/{dashboard_id}"
        result = api_request(url, config['api_key'], method="PUT", data=json_def)
        
        logger.info(f"✅ Dashboard {dashboard_id} updated: {config['url']}/dashboard/{dashboard_id}")
        
        return dashboard
