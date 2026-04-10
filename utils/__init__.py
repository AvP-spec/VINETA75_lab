print(f"package '\033[92m'utils'\033[0m' from AvP")
import os
import sys


file_dir = os.path.dirname(os.path.abspath(__file__))
if file_dir not in sys.path:
    sys.path.insert(0, file_dir)