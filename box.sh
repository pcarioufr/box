#!/bin/bash
# Unified runner for data tools (Jira, Confluence, Snowflake)
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
    echo "  jira fetch               Fetch Jira tickets using REST API v3"
    echo "  google pull              Pull a Google Doc as local markdown"
    echo "  confluence pull|clean    Pull Confluence pages as local markdown"
    echo "  snowflake query          Execute Snowflake SQL queries from files"
    echo "  snowflake discover       Explore Snowflake schemas, tables, and columns"
    echo "  datadog rum query        Query Datadog RUM events"
    echo "  datadog rum aggregate    Aggregate RUM data (top N, time series)"
    echo "  datadog notebook create  Create Datadog notebook from JSON"
    echo "  datadog notebook update  Update existing Datadog notebook"
    echo "  datadog fetch session    Fetch RUM session timeline as YAML"
    echo "  datadog fetch sessions   Fetch multiple sessions (by session or view query)"
    echo "  datadog fetch view       Fetch raw RUM view attributes as YAML"
    echo "  excalidraw [open|api|stop]  Diagrams with Excalidraw (YAML push workflow)"
    echo "  metabase dashboard       Pull/push Metabase dashboards (YAML format)"
    echo "  analysis compare         A/B test comparison with statistical tests"
    echo "  analysis analyze         Exploratory analysis with clustering"
    echo ""
    echo "Quick Start:"
    echo "  ./box.sh --setup                                             # First-time setup"
    echo "  ./box.sh jira fetch FRMNTS --max-results 100 -o tickets.json # Fetch tickets"
    echo "  ./box.sh google pull <id> -o data/doc.md                      # Pull a Google Doc"
    echo "  ./box.sh confluence pull <url> -o data/project/               # Pull Confluence page"
    echo "  ./box.sh confluence clean input.md -o clean.md               # Clean markdown"
    echo "  ./box.sh snowflake query analysis.sql                        # Execute SQL query"
    echo "  ./box.sh snowflake discover tables monitor                   # Find tables matching 'monitor'"
    echo "  ./box.sh datadog rum query \"@type:view\" --from-time 1h      # Query RUM events"
    echo "  ./box.sh excalidraw                                           # Start Excalidraw"
    echo "  ./box.sh excalidraw api push diagram.yaml                    # Push YAML diagram"
    echo "  ./box.sh metabase dashboard pull 75122 --dir my-dashboard/   # Pull Metabase dashboard"
    echo "  ./box.sh metabase dashboard push --dir my-dashboard/         # Push dashboard changes"
    echo "  ./box.sh analysis compare --entities data.csv --metrics m.yaml  # A/B test comparison"
    echo "  ./box.sh analysis analyze --entities data.csv --clusters 3   # Exploratory analysis"
    echo ""
    echo "For detailed help:"
    echo "  ./box.sh jira --help"
    echo "  ./box.sh google --help"
    echo "  ./box.sh confluence --help"
    echo "  ./box.sh snowflake --help"
    echo "  ./box.sh datadog --help"
    echo "  ./box.sh metabase --help"
    echo "  ./box.sh analysis --help"
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

    # Export environment variables to ~/.zprofile for MCP servers
    log_section "🔑 Shell Environment Variables"

    ZPROFILE="$HOME/.zprofile"

    if [ -f "$ENV_FILE" ]; then
        info "Checking environment variables from .env..."

        # Variables that MCP servers need in the shell environment
        MCP_VARS=(SNOWFLAKE_ACCOUNT SNOWFLAKE_USER SNOWFLAKE_DATABASE SNOWFLAKE_WAREHOUSE)

        VARS_TO_ADD=()
        VARS_TO_OVERRIDE=()

        for var_name in "${MCP_VARS[@]}"; do
            # Read value from .env
            var_value=$(grep -E "^${var_name}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-)
            if [ -z "$var_value" ]; then
                continue
            fi

            # Check if already in .zprofile
            existing=$(grep -E "^export ${var_name}=" "$ZPROFILE" 2>/dev/null | head -1 | sed "s/^export ${var_name}=//" || true)
            if [ -n "$existing" ] && [ "$existing" != "$var_value" ]; then
                VARS_TO_OVERRIDE+=("$var_name")
            elif [ -z "$existing" ]; then
                VARS_TO_ADD+=("$var_name")
            else
                success "  ✅ $var_name (already set)"
            fi
        done

        # Handle variables that need overriding
        for var_name in "${VARS_TO_OVERRIDE[@]}"; do
            var_value=$(grep -E "^${var_name}=" "$ENV_FILE" | head -1 | cut -d'=' -f2-)
            existing=$(grep -E "^export ${var_name}=" "$ZPROFILE" | head -1 | sed "s/^export ${var_name}=//")
            warning "  ⚠️  $var_name already exists in $ZPROFILE"
            echo "     Current: $existing"
            echo "     New:     $var_value"
            read -p "     Override? (y/N) " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                sed -i '' "s|^export ${var_name}=.*|export ${var_name}=${var_value}|" "$ZPROFILE"
                success "  ✅ $var_name (updated)"
            else
                info "  ⏭  $var_name (skipped)"
            fi
        done

        # Add new variables
        if [ ${#VARS_TO_ADD[@]} -gt 0 ]; then
            # Add a section header if this is the first time
            if ! grep -q "# Box CLI environment" "$ZPROFILE" 2>/dev/null; then
                echo "" >> "$ZPROFILE"
                echo "# Box CLI environment (added by ./box.sh --setup)" >> "$ZPROFILE"
            fi

            for var_name in "${VARS_TO_ADD[@]}"; do
                var_value=$(grep -E "^${var_name}=" "$ENV_FILE" | head -1 | cut -d'=' -f2-)
                echo "export ${var_name}=${var_value}" >> "$ZPROFILE"
                success "  ✅ $var_name (added to ~/.zprofile)"
            done
        fi

        if [ ${#VARS_TO_ADD[@]} -eq 0 ] && [ ${#VARS_TO_OVERRIDE[@]} -eq 0 ]; then
            success "All MCP environment variables already configured."
        else
            echo ""
            info "Restart your terminal or run: source ~/.zprofile"
        fi
    else
        warning "No .env file found — skipping shell environment setup."
        info "Run setup again after creating .env to configure shell variables."
    fi

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

    metabase)
        # Metabase dashboard management
        "$SHARED_VENV/bin/python" -m libs.metabase "$@"
        exit $?
        ;;

    analysis)
        # Statistical analysis for CSV data
        "$SHARED_VENV/bin/python" -m libs.analysis "$@"
        exit $?
        ;;

    excalidraw|draw)
        # Excalidraw diagrams
        COMPOSE_FILE="$SCRIPT_DIR/services/compose.yml"
        SUBCOMMAND="${1:-open}"

        _ensure_excalidraw() {
            if ! docker compose -f "$COMPOSE_FILE" ps excalidraw --format '{{.State}}' 2>/dev/null | grep -q running; then
                info "Starting Excalidraw Canvas Server..."
                docker compose -f "$COMPOSE_FILE" up excalidraw -d --quiet-pull 2>/dev/null
                sleep 2
            fi
        }

        case "$SUBCOMMAND" in
            open|"")
                _ensure_excalidraw
                success "Excalidraw running at http://localhost:3000"
                open "http://localhost:3000" 2>/dev/null || xdg-open "http://localhost:3000" 2>/dev/null || echo "Open http://localhost:3000 in your browser"
                ;;
            api)
                _ensure_excalidraw
                shift
                "$SHARED_VENV/bin/python" -m libs.excalidraw "$@"
                exit $?
                ;;
            stop)
                info "Stopping Excalidraw..."
                docker compose -f "$COMPOSE_FILE" stop excalidraw
                success "Excalidraw stopped"
                ;;
            *)
                echo "Usage: ./box.sh excalidraw [open|api|stop]"
                echo "  open          Start Excalidraw and open browser (default)"
                echo "  api <cmd>     Canvas API (health, query, push, clear, yaml)"
                echo "  stop          Stop Excalidraw container"
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
