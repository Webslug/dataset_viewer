"""Local server for Dataset Viewer.

Run ``python3 server.py`` and open the configured local URL it prints. Project
manifests are stored in ``projects/`` and are the allow-list for dataset access.
"""
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json
import os
import re
import subprocess
import tempfile

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.json"
PROJECTS_DIR = PROJECT_DIR / "projects"
PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
MAX_REQUEST_BYTES = 1_000_000
DEFAULT_PORT = 8134


def read_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def write_json(path, payload):
    """Replace JSON atomically so a stopped save does not corrupt a manifest."""
    descriptor, temporary_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(payload, target, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise


def safe_project_name(value):
    if not isinstance(value, str) or not PROJECT_NAME.fullmatch(value):
        raise ValueError("Project names may contain letters, numbers, hyphens, and underscores.")
    return value


def configured_port(config):
    """Return the configured local port, constrained to the project range."""
    port = config.get("port", DEFAULT_PORT)
    if isinstance(port, bool) or not isinstance(port, int) or not 8000 <= port <= 8999:
        raise ValueError("config.json port must be an integer from 8000 to 8999.")
    return port


def entry_count(data):
    entries = data.get("examples", data.get("entries", [])) if isinstance(data, dict) else []
    return len(entries) if isinstance(entries, list) else 0


def dataset_path(value):
    """Resolve absolute paths or project-root-relative paths from a manifest."""
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_DIR / path).resolve()


def load_active_project(project_name=None):
    """Load manifest datasets, silently skipping inaccessible dataset files."""
    config = read_json(CONFIG_PATH)
    project_name = safe_project_name(project_name or config["last_project"])
    manifest = read_json(PROJECTS_DIR / f"{project_name}.json")
    error_count = 0
    datasets = []
    for item in manifest.get("datasets", []):
        try:
            path = dataset_path(item["path"])
            data = read_json(path)
            datasets.append({
                "id": item["id"],
                "label": item.get("label", path.name),
                "description": item.get("description", "Dataset file"),
                "file": str(path),
                "entry_count": entry_count(data),
                "path": str(path),
            })
        except (KeyError, OSError, json.JSONDecodeError, TypeError):
            error_count += 1
    return config, {
        "id": project_name,
        "name": manifest.get("name", project_name),
        "theme": config.get("theme", "green-grid.css"),
        "ui_layout": config.get("ui_layout", {}),
        "datasets": datasets,
        "layout": manifest.get("layout", {}),
        "metadata": manifest.get("metadata", {}),
        "modified": (PROJECTS_DIR / f"{project_name}.json").stat().st_mtime,
        "error_count": error_count,
    }


def list_projects():
    projects = []
    for path in PROJECTS_DIR.glob("*.json"):
        try:
            manifest = read_json(path)
            projects.append({
                "id": path.stem,
                "name": manifest.get("name", path.stem),
                "modified": path.stat().st_mtime,
                "metadata": manifest.get("metadata", {}),
            })
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return sorted(projects, key=lambda project: project["modified"], reverse=True)


def save_project(project_name, payload):
    """Validate and save a project manifest inside projects/ only."""
    project_name = safe_project_name(project_name)
    if not isinstance(payload, dict) or not isinstance(payload.get("datasets"), list):
        raise ValueError("A project must contain a dataset list.")
    project_title = payload.get("name", project_name)
    if not isinstance(project_title, str) or not project_title.strip() or len(project_title) > 120:
        raise ValueError("Project name must be non-empty text up to 120 characters.")
    datasets = []
    dataset_ids = set()
    for item in payload["datasets"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("id", "label", "description", "path")):
            raise ValueError("Each dataset needs an id, label, description, and path.")
        if not item["id"] or item["id"] in dataset_ids:
            raise ValueError("Dataset ids must be unique and non-empty.")
        dataset_ids.add(item["id"])
        datasets.append({key: item[key] for key in ("id", "label", "description", "path")})
    layout = payload.get("layout", {})
    if not isinstance(layout, dict):
        raise ValueError("Project layout must be an object.")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict) or not all(isinstance(value, str) for value in metadata.values()):
        raise ValueError("Project metadata must contain text values.")
    manifest = {"name": project_title.strip(), "metadata": metadata, "datasets": datasets, "layout": layout}
    write_json(PROJECTS_DIR / f"{project_name}.json", manifest)
    config = read_json(CONFIG_PATH)
    config["last_project"] = project_name
    write_json(CONFIG_PATH, config)
    return project_name


class Handler(SimpleHTTPRequestHandler):
    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def request_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise ValueError("Request body must be between 1 and 1,000,000 bytes.")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def do_GET(self):
        request = urlparse(self.path)
        if request.path == "/api/project":
            try:
                project_name = parse_qs(request.query).get("name", [None])[0]
                _, project = load_active_project(project_name)
                self.send_json(project)
            except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError):
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Project configuration is invalid.")
            return
        if request.path == "/api/projects":
            self.send_json({"projects": list_projects()})
            return
        super().do_GET()

    def do_POST(self):
        request = urlparse(self.path)
        try:
            payload = self.request_json()
            if request.path == "/api/open":
                config, project = load_active_project()
                target = next(dataset for dataset in project["datasets"] if dataset["id"] == payload["id"])
                editor = config["editor"]
                command, arguments = editor["command"], editor.get("arguments", [])
                if not isinstance(command, str) or not isinstance(arguments, list) or not all(isinstance(arg, str) for arg in arguments):
                    raise ValueError("Invalid editor configuration.")
                subprocess.Popen([command, *arguments, target["path"]], start_new_session=True)
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            if request.path == "/api/projects":
                project_name = save_project(payload["id"], payload["project"])
                _, project = load_active_project(project_name)
                self.send_json(project, HTTPStatus.CREATED)
                return
            if request.path == "/api/select-project":
                project_name = safe_project_name(payload["id"])
                load_active_project(project_name)
                config = read_json(CONFIG_PATH)
                config["last_project"] = project_name
                write_json(CONFIG_PATH, config)
                self.send_json({"id": project_name})
                return
            if request.path == "/api/reveal-project":
                project_name = safe_project_name(payload["id"])
                target = PROJECTS_DIR / f"{project_name}.json"
                if not target.is_file():
                    raise ValueError("Project manifest was not found.")
                subprocess.Popen(["xdg-open", str(PROJECTS_DIR)], start_new_session=True)
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (KeyError, StopIteration, ValueError, OSError, json.JSONDecodeError, TypeError) as error:
            self.send_error(HTTPStatus.BAD_REQUEST, str(error))


if __name__ == "__main__":
    port = configured_port(read_json(CONFIG_PATH))
    print(f"Dataset Viewer: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
