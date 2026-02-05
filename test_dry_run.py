#!/usr/bin/env python3
"""Test dry run mode functionality"""
import sys

# Test that the argument parsing works
print("Testing dry run mode argument parsing...")

# Test --help
print("\n" + "="*60)
print("Testing --help flag:")
print("="*60)
import subprocess
result = subprocess.run(
    ['python', 'src/main.py', '--help'],
    capture_output=True,
    text=True
)
print(result.stdout)

if '--dry-run' in result.stdout and 'no data written' in result.stdout.lower():
    print("✅ Help text includes dry-run information")
else:
    print("❌ Help text missing dry-run information")
    sys.exit(1)

print("\n" + "="*60)
print("Dry run mode is available!")
print("="*60)
print("\nUsage:")
print("  python src/main.py --dry-run    # Test mode")
print("  python src/main.py -d           # Test mode (short)")
print("  python src/main.py              # Normal mode")
