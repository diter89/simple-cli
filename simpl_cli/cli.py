#!/usr/bin/env python3
import os
import sys


def main():
    try:
        package_root = os.path.dirname(os.path.abspath(__file__))
        if package_root not in sys.path:
            sys.path.insert(0, package_root)

        from simpl_cli import app

        if hasattr(app, "main"):
            return app.main()

        print("Error: No main() function found in app.py")
        return 1

    except KeyboardInterrupt:
        print("\nBye!")
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
