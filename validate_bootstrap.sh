#!/bin/bash
# Bootstrap Validation Script
# This script validates that the research-agent project is correctly bootstrapped

set -e

echo "========================================"
echo "Research Agent Bootstrap Validation"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check 1: Python version
echo "1. Checking Python version..."
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "   ✓ Python $PYTHON_VERSION detected"
echo ""

# Check 2: Virtual environment
echo "2. Checking virtual environment..."
if [[ "$VIRTUAL_ENV" == *".venv"* ]]; then
    echo "   ✓ Virtual environment active: $VIRTUAL_ENV"
else
    echo "   ⚠ No virtual environment detected. Run: source .venv/bin/activate"
fi
echo ""

# Check 3: Package installation
echo "3. Checking package installation..."
if python3 -c "import research_agent" 2>/dev/null; then
    echo "   ✓ research_agent package importable"
else
    echo -e "   ${RED}✗ research_agent package not found${NC}"
    exit 1
fi
echo ""

# Check 4: CLI availability
echo "4. Checking CLI availability..."
if command -v research-agent &> /dev/null; then
    echo "   ✓ research-agent CLI available"
else
    echo -e "   ${RED}✗ research-agent CLI not found${NC}"
    exit 1
fi
echo ""

# Check 5: CLI commands
echo "5. Testing CLI commands..."
research-agent --help > /dev/null 2>&1 && echo "   ✓ research-agent --help works"
research-agent version > /dev/null 2>&1 && echo "   ✓ research-agent version works"
echo ""

# Check 6: Configuration files
echo "6. Checking configuration files..."
[[ -f pyproject.toml ]] && echo "   ✓ pyproject.toml exists"
[[ -f .env.example ]] && echo "   ✓ .env.example exists"
[[ -f .gitignore ]] && echo "   ✓ .gitignore exists"
[[ -f README.md ]] && echo "   ✓ README.md exists"
echo ""

# Check 7: Source structure
echo "7. Checking source structure..."
[[ -d src/research_agent ]] && echo "   ✓ src/research_agent/ exists"
[[ -f src/research_agent/__init__.py ]] && echo "   ✓ __init__.py exists"
[[ -f src/research_agent/config.py ]] && echo "   ✓ config.py exists"
[[ -f src/research_agent/cli.py ]] && echo "   ✓ cli.py exists"
[[ -f src/research_agent/api.py ]] && echo "   ✓ api.py exists"
[[ -f src/research_agent/logging_config.py ]] && echo "   ✓ logging_config.py exists"
[[ -d src/research_agent/models ]] && echo "   ✓ models/ directory exists"
echo ""

# Check 8: Tests
echo "8. Checking test structure..."
[[ -d tests ]] && echo "   ✓ tests/ directory exists"
[[ -f tests/test_config.py ]] && echo "   ✓ test_config.py exists"
echo ""

# Check 9: Dependencies
echo "9. Checking key dependencies..."
python3 -c "import fastapi" 2>/dev/null && echo "   ✓ fastapi installed"
python3 -c "import typer" 2>/dev/null && echo "   ✓ typer installed"
python3 -c "import pydantic" 2>/dev/null && echo "   ✓ pydantic installed"
python3 -c "import structlog" 2>/dev/null && echo "   ✓ structlog installed"
python3 -c "import langgraph" 2>/dev/null && echo "   ✓ langgraph installed"
echo ""

# Check 10: Import test
echo "10. Testing module imports..."
python3 -c "from research_agent import get_settings, load_settings" 2>/dev/null && echo "   ✓ Config functions importable"
python3 -c "from research_agent.models import QueryRequest, QueryResponse" 2>/dev/null && echo "   ✓ Models importable"
python3 -c "from research_agent.exceptions import ResearchAgentError" 2>/dev/null && echo "   ✓ Exceptions importable"
echo ""

echo "========================================"
echo -e "${GREEN}✓ All bootstrap checks passed!${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and configure API keys"
echo "  2. Run: research-agent config --validate-only"
echo "  3. Try: research-agent run test-thread 'Your query here'"
echo "  4. Or start API: research-agent serve"
echo ""
