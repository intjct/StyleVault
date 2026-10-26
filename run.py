# Entry point used to build StyleVault.exe with PyInstaller.
import sys

from stylevault.app import main

if __name__ == "__main__":
    sys.exit(main())
