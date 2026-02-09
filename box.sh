#!/bin/bash
# Unified runner for data tools (Jira, Confluence, Snowflake, Ubuntu)
# Handles setup, venv activation, and dispatches to CLI

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIBS_DIR="$SCRIPT_DIR/libs"
SHARED_VENV="$SCRIPT_DIR/.venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
ENV_FILE="$SCRIPT_DIR/.env"

# Output functions
error() {
    echo -e "\033[0;31m$1\033[0m"
}

warning() {
    echo -e "\033[1;33m$1\033[0m"
}

success() {
    echo -e "\033[0;32m$1\033[0m"
}

info() {
    echo -e "$1"
}

log_section() {
    echo ""
    echo -e "\033[0;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
    echo -e "\033[0;34m$1\033[0m"
    echo -e "\033[0;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
    echo ""
}

usage() {
    echo "Usage: ./box.sh <command> [args...]"
    echo "       ./box.sh --setup"
    echo ""
    echo "Setup:"
    echo "  --setup                  Initialize virtual environment and install dependencies"
    echo ""
    echo "Commands:"
    echo "  ubuntu [args]            Run commands in Ubuntu container (or open shell)"
    echo "  jira fetch               Fetch Jira tickets using REST API v3"
    echo "  google list|add|refresh  Sync Google Docs to local markdown"
    echo "  confluence list|add|...  Sync Confluence pages to local markdown"
    echo "  snowflake query          Execute Snowflake SQL queries from files"
    echo "  datadog rum query        Query Datadog RUM events"
    echo "  datadog rum aggregate    Aggregate RUM data (top N, time series)"
    echo "  datadog notebook create  Create Datadog notebook from JSON"
    echo "  datadog notebook update  Update existing Datadog notebook"
    echo "  datadog fetch session    Fetch RUM session timeline as YAML"
    echo "  datadog fetch sessions   Fetch multiple sessions (by session or view query)"
    echo "  datadog fetch view       Fetch raw RUM view attributes as YAML"
    echo "  draw [open|api|stop]     Diagrams with Excalidraw (YAML push workflow)"
    echo ""
    echo "Quick Start:"
    echo "  ./box.sh --setup                                             # First-time setup"
    echo "  ./box.sh ubuntu                                              # Open Ubuntu shell"
    echo "  ./box.sh jira fetch FRMNTS --max-results 100 -o tickets.json # Fetch tickets"
    echo "  ./box.sh google refresh                                      # Sync all Google Docs"
    echo "  ./box.sh confluence download <url> --name my-page            # Download Confluence page"
    echo "  ./box.sh confluence clean input.md -o clean.md               # Clean markdown"
    echo "  ./box.sh snowflake query analysis.sql --format json          # Execute SQL query"
    echo "  ./box.sh datadog rum query \"@type:view\" --from-time 1h      # Query RUM events"
    echo "  ./box.sh draw                                                # Start Excalidraw"
    echo "  ./box.sh draw api push diagram.yaml                            # Push YAML diagram"
    echo ""
    echo "For detailed help:"
    echo "  ./box.sh jira --help"
    echo "  ./box.sh google --help"
    echo "  ./box.sh confluence --help"
    echo "  ./box.sh snowflake --help"
    echo "  ./box.sh datadog --help"
    echo ""
}

# Check if command specified
if [ $# -eq 0 ]; then
    error "No command specified"
    echo ""
    usage
    exit 1
fi

COMMAND="$1"
shift  # Remove first arg, rest are command args

# Setup function
run_setup() {
    log_section "🚀 Data Tools Setup"

    # Check Python version
    info "Checking Python version..."
    if ! command -v python3 &> /dev/null; then
        error "python3 not found. Please install Python 3.11 or higher."
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    info "Found Python $PYTHON_VERSION"

    # Verify Python 3.11+
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
        error "Python 3.11 or higher is required (found $PYTHON_VERSION)"
        exit 1
    fi

    # Create shared virtual environment
    if [ -d "$SHARED_VENV" ]; then
        warning "Virtual environment already exists at $SHARED_VENV"
        read -p "   Do you want to recreate it? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            info "Removing existing virtual environment..."
            rm -rf "$SHARED_VENV"
        else
            info "Keeping existing virtual environment."
        fi
    fi

    if [ ! -d "$SHARED_VENV" ]; then
        info "Creating virtual environment at $SHARED_VENV..."
        python3 -m venv "$SHARED_VENV"
        success "✅ Virtual environment created"
    fi

    # Activate virtual environment
    info "Activating virtual environment..."
    source "$SHARED_VENV/bin/activate"

    # Upgrade pip
    info "Upgrading pip..."
    pip install --upgrade pip --quiet
    success "✅ pip upgraded"

    # Install dependencies
    info "Installing dependencies from $REQUIREMENTS_FILE..."
    pip install -r "$REQUIREMENTS_FILE"
    success "✅ All dependencies installed"

    # Verify installations
    log_section "🔍 Verifying Installations"

    if python -c "import requests" 2>/dev/null; then
        success "✅ requests"
    else
        error "Failed to import requests"
        exit 1
    fi

    success "✅ Data tools setup complete"

    deactivate

    # Final summary
    log_section "✅ Setup Complete! 🎉"

    echo ""
    echo "Virtual environment: $SHARED_VENV"
    echo ""

    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        warning "⚠️  Next step: Configure Atlassian credentials"
        echo ""
        echo "  1. Copy env.example to .env:"
        echo "     cp env.example .env"
        echo ""
        echo "  2. Edit .env and add your Atlassian credentials:"
        echo "     - JIRA_EMAIL: your.email@datadog.com"
        echo "     - JIRA_TOKEN: your-api-token"
        echo ""
        echo "  3. Create API token at:"
        echo "     https://id.atlassian.com/manage-profile/security/api-tokens"
        echo ""
    else
        success "✅ Atlassian credentials configured (.env file found)"
        echo ""
    fi

    echo "Test the CLI:"
    echo "  ./box.sh jira --help"
    echo "  ./box.sh jira fetch --help"
    echo "  ./box.sh confluence --help"
    echo "  ./box.sh confluence clean --help"
    echo "  ./box.sh snowflake --help"
    echo ""
}

# Handle --setup flag
if [ "$COMMAND" = "--setup" ]; then
    run_setup
    exit 0
fi

# Load environment variables from .env if it exists
if [ -f "$ENV_FILE" ]; then
    set -a  # Automatically export all variables
    source "$ENV_FILE"
    set +a  # Stop automatically exporting
fi

# Handle commands
case "$COMMAND" in
    ubuntu)
        # Dispatch to ubuntu service runner
        "$SCRIPT_DIR/services/ubuntu/run.sh" "$@"
        exit $?
        ;;

    jira)
        # Jira ticket fetching
        "$SHARED_VENV/bin/python" -m libs.jira "$@"
        exit $?
        ;;

    google)
        # Google Docs sync
        "$SHARED_VENV/bin/python" -m libs.google "$@"
        exit $?
        ;;

    confluence)
        # Confluence page sync and download
        "$SHARED_VENV/bin/python" -m libs.confluence "$@"
        exit $?
        ;;

    snowflake)
        # Snowflake query execution
        "$SHARED_VENV/bin/python" -m libs.snowflake "$@"
        exit $?
        ;;

    datadog)
        # Datadog RUM queries
        "$SHARED_VENV/bin/python" -m libs.datadog "$@"
        exit $?
        ;;

    draw)
        # Excalidraw diagrams
        DIAGRAMS_DIR="$SCRIPT_DIR/data/diagrams"
        COMPOSE_FILE="$SCRIPT_DIR/services/compose.yml"
        SUBCOMMAND="${1:-open}"

        case "$SUBCOMMAND" in
            open|"")
                # Start excalidraw and open browser
                info "Starting Excalidraw Canvas Server..."
                docker compose -f "$COMPOSE_FILE" up excalidraw -d --quiet-pull 2>/dev/null
                sleep 2
                success "Excalidraw running at http://localhost:3000"
                info "Opening browser..."
                open "http://localhost:3000" 2>/dev/null || xdg-open "http://localhost:3000" 2>/dev/null || echo "Open http://localhost:3000 in your browser"
                info ""
                info "Claude can interact via: ./box.sh draw api <command>"
                info "Diagrams saved to: $DIAGRAMS_DIR"
                ;;
            api)
                # Auto-start container if not running
                if ! docker compose -f "$COMPOSE_FILE" ps excalidraw --format '{{.State}}' 2>/dev/null | grep -q running; then
                    info "Starting Excalidraw Canvas Server..."
                    docker compose -f "$COMPOSE_FILE" up excalidraw -d --quiet-pull 2>/dev/null
                    sleep 2
                fi
                # Pass to Python CLI for API operations
                shift  # Remove 'api' from args
                "$SHARED_VENV/bin/python" -m libs.excalidraw "$@"
                exit $?
                ;;
            new)
                NAME="${2:-diagram}"
                mkdir -p "$DIAGRAMS_DIR"
                FILEPATH="$DIAGRAMS_DIR/$NAME.excalidraw"
                if [ -f "$FILEPATH" ]; then
                    error "File already exists: $FILEPATH"
                    exit 1
                fi
                cat > "$FILEPATH" << 'TEMPLATE'
{
  "type": "excalidraw",
  "version": 2,
  "source": "box-cli",
  "elements": [],
  "appState": {
    "gridSize": null,
    "viewBackgroundColor": "#ffffff"
  },
  "files": {}
}
TEMPLATE
                success "Created: $FILEPATH"
                ;;
            list)
                mkdir -p "$DIAGRAMS_DIR"
                info "Diagrams in $DIAGRAMS_DIR:"
                ls -la "$DIAGRAMS_DIR"/*.excalidraw 2>/dev/null || info "  (none yet)"
                ;;
            stop)
                info "Stopping Excalidraw..."
                docker compose -f "$COMPOSE_FILE" stop excalidraw
                success "Excalidraw stopped"
                ;;
            *)
                echo "Usage: ./box.sh draw [open|api|new|list|stop]"
                echo ""
                echo "Commands:"
                echo "  open              Start Excalidraw and open browser (default)"
                echo "  api <cmd>         Canvas API (health, query, push, clear, yaml)"
                echo "  new <name>        Create new .excalidraw file"
                echo "  list              List diagrams in data/diagrams/"
                echo "  stop              Stop Excalidraw container"
                echo ""
                echo "API Examples:"
                echo "  ./box.sh draw api health                    # Check server status"
                echo "  ./box.sh draw api query                     # List elements on canvas"
                echo "  ./box.sh draw api push data/diagrams/arch.yaml  # Push YAML diagram"
                echo "  ./box.sh draw api push arch.yaml --clear        # Full clear + push"
                echo "  ./box.sh draw api clear                     # Clear all elements"
                echo "  ./box.sh draw api yaml                      # YAML format reference"
                exit 1
                ;;
        esac
        exit 0
        ;;

    -h|--help|help)
        usage
        exit 0
        ;;

    *)
        error "Unknown command '$COMMAND'"
        echo ""
        usage
        exit 1
        ;;
esac
