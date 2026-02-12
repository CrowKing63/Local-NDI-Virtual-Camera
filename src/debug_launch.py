import sys
import os
import logging

# Ensure src is in path
sys.path.append(os.getcwd())

print("--- DEBUG LAUNCHER ---")
print(f"CWD: {os.getcwd()}")
print(f"Python: {sys.executable}")

try:
    from src import config
    print(f"Config loaded. FFMPEG_BIN: {config.FFMPEG_BIN}")
except Exception as e:
    print(f"Failed to import config: {e}")
    sys.exit(1)

try:
    from src.main import main
    print("Imported main successfully.")
except Exception as e:
    print(f"Failed to import main: {e}")
    sys.exit(1)

print("Calling main()...")
try:
    main()
except Exception as e:
    print(f"CRASH in main(): {e}")
except SystemExit as e:
    print(f"SystemExit in main(): {e}")

print("--- APP EXIT ---")
