"""Write the OpenAPI schema to a file. The web client types are generated from it."""

import json
import sys
from pathlib import Path

from careerpilot.core.config import Settings
from careerpilot.main import create_app


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    # The engine never connects, so a placeholder URL is enough to build the app.
    app = create_app(Settings(database_url="postgresql+asyncpg://unused@127.0.0.1/unused"))
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
