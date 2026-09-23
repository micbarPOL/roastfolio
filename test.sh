#!/usr/bin/env bash
set -e

# Detect pytest binary
if [ -f ".venv/bin/pytest" ]; then
    PYTEST=".venv/bin/pytest"
else
    PYTEST="pytest"
fi

COMMAND="${1:-smoke}"

SMOKE_FILES=(
    "tests/test_footer_and_release_contract.py"
    "tests/test_dashboard_ui_contract.py"
    "tests/test_guide_mobile_contract.py"
    "tests/test_monthly_audit_ui_contract.py"
    "tests/test_mobile_benchmark_contract.py"
    "tests/test_template_contract.py"
    "tests/test_portfolio_editor_contract.py"
    "tests/test_retirement_chart_contract.py"
    "tests/test_retirement_simulation_contract.py"
    "tests/test_transaction_inline_layout.py"
    "tests/test_prompt_builder.py"
)

case "$COMMAND" in
    smoke|ui)
        echo "⚡ Running smoke tests (< 1s)..."
        exec $PYTEST "${SMOKE_FILES[@]}" "${@:2}"
        ;;
    full|calc|backend)
        echo "🧪 Running full logic and calculation tests..."
        exec $PYTEST -m full "${@:2}"
        ;;
    browser)
        echo "🌐 Running Playwright browser regressions..."
        exec $PYTEST tests/test_monthly_audit_browser.py tests/test_benchmark_consent_browser.py "${@:2}"
        ;;
    all)
        echo "🚀 Running all tests..."
        exec $PYTEST "$@"
        ;;
    help|--help|-h)
        echo "Usage: ./test.sh [smoke|full|browser|all] [pytest-options]"
        echo ""
        echo "Subcommands:"
        echo "  smoke (or ui): Fast UI contract & template tests (< 1s). Run after UI/CSS changes."
        echo "  full:          Comprehensive financial calculation & backend tests (excluding browser)."
        echo "  browser:       Playwright browser regressions."
        echo "  all:           Run entire test suite."
        exit 0
        ;;
    *)
        echo "Unknown test command: $COMMAND"
        echo "Usage: ./test.sh [smoke|full|browser|all]"
        exit 1
        ;;
esac
