import os
import sys
import subprocess

script_name = "QFP_main.py"
icon_name = "favicon.ico"

command = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--noconsole",
    "--onefile",
    "--name=QFP Gold Edition",
    f"--icon={icon_name}",
    f"--add-data={icon_name};.",
    script_name,
]

try:
    print("Compiling application...")
    subprocess.run(command, check=True)
    print("\nYayyyy! Compilation successful.")
except subprocess.CalledProcessError:
    print("\nUh oh. PyInstaller failed to compile.")
except FileNotFoundError:
    print("\nYou don't have PyInstaller installed.")

input("\nPress Enter to close...")
