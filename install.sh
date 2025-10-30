#!/bin/bash

# Merit Analyzer Installation Script

echo "🚀 Installing Merit Analyzer..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.9 or higher is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Install the package
echo "📦 Installing Merit Analyzer..."
pip3 install -e .

if [ $? -eq 0 ]; then
    echo "✅ Merit Analyzer installed successfully!"
    echo ""
    echo "🎉 Installation complete!"
    echo ""
    echo "Next steps:"
    echo "1. Set your Anthropic API key: export ANTHROPIC_API_KEY='your-key-here'"
    echo "2. Run a quick test: merit-analyze --help"
    echo "3. Try the example: python examples/basic_usage.py"
    echo ""
    echo "📚 Documentation: https://github.com/merit-analyzer/merit-analyzer"
else
    echo "❌ Installation failed. Please check the error messages above."
    exit 1
fi
