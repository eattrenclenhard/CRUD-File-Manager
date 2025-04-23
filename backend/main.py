import logging
import os
import toml
from flask import Flask, jsonify, request
from vuefinder import VuefinderApp, fill_fs
from fs.memoryfs import MemoryFS
from fs.wrap import WrapReadOnly
from fs.osfs import OSFS
from waitress import serve
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("waitress")

# Load environment variables
load_dotenv()
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.error("API_KEY is not set in the environment. API requests will fail without a valid key.")

# Initialize Flask app for REST API
api = Flask(__name__)

# Middleware to enforce API key requirement
@api.before_request
def require_api_key():
    api_key = request.headers.get("x-api-key")
    if api_key != API_KEY:
        return jsonify({"error": "Unauthorized: Invalid API Key"}), 401

# Load user configuration from TOML file
def load_config(config_path="config.toml"):
    config_path = Path(config_path)
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found.")
        return []
    try:
        return toml.load(config_path).get("file_systems", [])
    except toml.TomlDecodeError as e:
        logger.error(f"Error parsing configuration file: {e}")
        return []


if __name__ == "__main__":
    virtual = MemoryFS()
    fill_fs(
        virtual,
        {
            "foo": {
                "file.txt": "Hello World!",
                "foo.txt": "foo bar baz",
                "bar": {"baz": None},
            },
            "foobar": {"empty": None, "hello.txt": "Hello!"},
        },
    )

    app = VuefinderApp(enable_cors=True)

    # Add the virtual directory manually
    app.add_fs("virtual_directory", virtual)

    # Load configuration for other file systems
    config = load_config()

    # Dynamically add file systems based on the configuration
    for entry in config:
        name = entry.get("name")
        read_only = entry.get("read_only", False)
        path = entry.get("path")

        if not name or not path:
            logger.warning(f"Invalid configuration entry: {entry}")
            continue

        path = Path(path)
        if not path.exists():
            logger.warning(f"Path '{path}' does not exist. Skipping '{name}'.")
            continue

        try:
            if read_only:
                app.add_fs(name, WrapReadOnly(OSFS(str(path))))
                logger.info(f"Added read-only file system: {name} -> {path}")
            else:
                app.add_fs(name, OSFS(str(path)))
                logger.info(f"Added read-write file system: {name} -> {path}")
        except Exception as e:
            logger.error(f"Failed to add file system '{name}': {e}")

    # REST API endpoint to list all file systems
    @api.route("/api/list_fs", methods=["GET"])
    def list_fs():
        """List all file systems added to the VuefinderApp instance."""
        try:
            file_systems = app._get_storages()  # Call the _get_storages method
            return jsonify({"file_systems": file_systems}), 200
        except Exception as e:
            logger.error(f"Error retrieving file systems: {e}")
            return jsonify({"error": "Failed to retrieve file systems"}), 500

    # Use Waitress to serve the application
    logger.info("Starting Waitress server on http://127.0.0.1:8005")
    serve(api, host="127.0.0.1", port=8005)
