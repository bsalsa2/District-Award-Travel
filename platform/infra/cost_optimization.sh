#!/bin/bash
#
# Cost Optimization Automation Script
# District Award Travel Infrastructure
#
# Automates the execution of cost optimization processes including:
# - Cost data collection
# - Analysis and reporting
# - Implementation of optimizations
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="/var/log/cost_optimization"
REPORT_DIR="/var/reports/cost_optimization"
CONFIG_FILE="${SCRIPT_DIR}/cost_optimization_config.json"

# Ensure directories exist
mkdir -p "$LOG_DIR"
mkdir -p "$REPORT_DIR"

# Logging function
log() {
    local level=$1
    local message=$2
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_DIR/cost_optimization_$(date +%Y%m%d).log"
}

# Error handling
handle_error() {
    local exit_code=$1
    local message=$2
    log "ERROR" "$message"
    exit $exit_code
}

# Load configuration
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        log "INFO" "Loading configuration from $CONFIG_FILE"
        # In a real implementation, we would parse the JSON config
        # For now, we'll use environment variables
        export AWS_COST_ANALYSIS_ENABLED="${AWS_COST_ANALYSIS_ENABLED:-true}"
        export GCP_COST_ANALYSIS_ENABLED="${GCP_COST_ANALYSIS_ENABLED:-true}"
        export COST_OPTIMIZATION_DRY_RUN="${COST_OPTIMIZATION_DRY_RUN:-false}"
        export COST_OPTIMIZATION_AUTO_APPLY="${COST_OPTIMIZATION_AUTO_APPLY:-false}"
        export COST_THRESHOLD_PERCENTAGE="${COST_THRESHOLD_PERCENTAGE:-5.0}"
    else
        log "WARN" "Configuration file $CONFIG_FILE not found, using environment variables"
    fi
}

# Check dependencies
check_dependencies() {
    local missing_deps=()

    # Check for Python
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi

    # Check for required Python packages
    if ! python3 -c "import boto3" 2> /dev/null; then
        missing_deps+=("boto3")
    fi

    if ! python3 -c "import google.cloud.billing_v1" 2> /dev/null; then
        missing_deps+=("google-cloud-billing")
    fi

    if [ ${#missing_deps[@]} -gt 0 ]; then
        log "ERROR" "Missing dependencies: ${missing_deps[*]}"
        log "INFO" "Install dependencies with: pip install ${missing_deps[*]}"
        return 1
    fi

    return 0
}

# Run cost optimization
run_optimization() {
    local mode=$1

    log "INFO" "Starting cost optimization process (mode: $mode)"

    # Activate virtual environment if it exists
    if [ -d "${PROJECT_ROOT}/.venv" ]; then
        log "INFO" "Activating virtual environment"
        source "${PROJECT_ROOT}/.venv/bin/activate" || handle_error 1 "Failed to activate virtual environment"
    fi

    # Run the Python cost optimization script
    log "INFO" "Executing cost optimization script"
    python3 "${SCRIPT_DIR}/cost_optimization.py" $mode || handle_error 1 "Cost optimization script failed"

    log "INFO" "Cost optimization process completed successfully"
}

# Main execution
main() {
    log "INFO" "=== District Award Travel Cost Optimization ==="
    log "INFO" "Starting execution at $(date)"

    # Load configuration
    load_config || handle_error 1 "Failed to load configuration"

    # Check dependencies
    check_dependencies || handle_error 1 "Dependency check failed"

    # Determine mode based on arguments
    local mode_args=""

    # Check for dry-run flag
    if [ "${COST_OPTIMIZATION_DRY_RUN,,}" = "true" ]; then
        mode_args="--dry-run"
        log "INFO" "Running in DRY RUN mode (no changes will be implemented)"
    fi

    # Check for force flag
    if [ "${COST_OPTIMIZATION_AUTO_APPLY,,}" = "true" ]; then
        mode_args="$mode_args --force"
        log "INFO" "Auto-apply mode enabled"
    fi

    # Run optimization
    run_optimization "$mode_args"

    log "INFO" "=== Cost Optimization Complete ==="
    log "INFO" "Reports available in: $REPORT_DIR"
    log "INFO" "Logs available in: $LOG_DIR"

    return 0
}

# Execute main function
main
