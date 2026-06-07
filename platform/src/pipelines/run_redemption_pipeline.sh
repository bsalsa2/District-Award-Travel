#!/bin/bash
# High-performance redemption tracking pipeline runner
# Optimized for mechanical sympathy and maximum throughput

set -euo pipefail

# Configuration
PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$PIPELINE_DIR")")"
VENV_DIR="$PROJECT_ROOT/.venv"

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    echo "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1-2)
if [ "$PYTHON_VERSION" != "3.11" ] && [ "$PYTHON_VERSION" != "3.10" ]; then
    echo "Warning: Python 3.10+ recommended for optimal performance"
fi

# Parse command line arguments
INPUT_SOURCE=""
OUTPUT_DB=""
BATCH_SIZE=1000
VERBOSE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input)
            INPUT_SOURCE="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DB="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$INPUT_SOURCE" ]; then
    echo "Error: --input source must be specified"
    echo "Usage: $0 --input <input_source> --output <output_db> [--batch-size N] [--verbose]"
    exit 1
fi

if [ -z "$OUTPUT_DB" ]; then
    echo "Error: --output database path must be specified"
    echo "Usage: $0 --input <input_source> --output <output_db> [--batch-size N] [--verbose]"
    exit 1
fi

# Create output directory if it doesn't exist
OUTPUT_DIR=$(dirname "$OUTPUT_DB")
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Creating output directory: $OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR"
fi

# Check if input file exists
if [[ "$INPUT_SOURCE" != "bigquery:"* ]] && [ ! -f "$INPUT_SOURCE" ]; then
    echo "Error: Input file not found: $INPUT_SOURCE"
    exit 1
fi

# Set up performance monitoring
if [ "$VERBOSE" = true ]; then
    echo "=== Redemption Tracking Pipeline ==="
    echo "Input source: $INPUT_SOURCE"
    echo "Output database: $OUTPUT_DB"
    echo "Batch size: $BATCH_SIZE"
    echo "Python version: $(python3 --version)"
    echo "Starting at: $(date)"
    echo "=================================="
fi

# Run the pipeline
if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would process redemption data from $INPUT_SOURCE to $OUTPUT_DB"
    echo "[DRY RUN] Batch size: $BATCH_SIZE"
    exit 0
fi

# Execute the pipeline with optimized settings
python3 -m platform.src.pipelines.redemption_tracking \
    --runner DirectRunner \
    --input "$INPUT_SOURCE" \
    --output "$OUTPUT_DB" \
    --batch_size "$BATCH_SIZE" \
    --tempLocation "/tmp/redemption-pipeline-${USER}-$(date +%s)" \
    --diskSizeGb 20 \
    --workerMachineType n1-standard-4 \
    --maxNumWorkers 8 \
    --experiments use_runner_v2 \
    --experiments use_portable_job_names

# Check pipeline status
PIPELINE_EXIT_CODE=$?
if [ $PIPELINE_EXIT_CODE -eq 0 ]; then
    if [ "$VERBOSE" = true ]; then
        echo "Pipeline completed successfully"
        echo "Database stats:"
        sqlite3 "$OUTPUT_DB" "SELECT COUNT(*) as total_redemptions FROM redemptions;"
    fi
else
    echo "Pipeline failed with exit code: $PIPELINE_EXIT_CODE"
    exit $PIPELINE_EXIT_CODE
fi
