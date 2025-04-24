import logging
import os
import toml
from flask import Flask, jsonify, request, Response
from vuefinder import VuefinderApp, fill_fs
from fs.memoryfs import MemoryFS
from fs.wrap import WrapReadOnly
from fs.osfs import OSFS
from waitress import serve
from pathlib import Path
from dotenv import load_dotenv
from uvicorn.middleware.wsgi import WSGIMiddleware
from werkzeug.wrappers import Request
from werkzeug.test import EnvironBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("waitress")

# Load environment variables
load_dotenv()
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.error(
        "API_KEY is not set in the environment. API requests will fail without a valid key."
    )

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


# Initialize VuefinderApp
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


# REST API endpoint to create a file or folder
@api.route("/api/create", methods=["POST"])
def create():
    """Create a new file or folder."""
    try:
        payload = request.json
        fs_name = payload.get("fs_name")
        path = payload.get("path")
        is_folder = payload.get("is_folder", False)

        logger.info(
            f"Create request received: fs_name={fs_name}, path={path}, is_folder={is_folder}"
        )

        if not fs_name or not path:
            return jsonify({"error": "fs_name and path are required"}), 400

        if is_folder:
            result = app.create_new_folder(
                fs_name=fs_name, path=path, name=path)
        else:
            result = app.create_new_file(fs_name=fs_name, path=path, name=path)

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result), 201

    except Exception as e:
        logger.error(f"Error creating file or folder: {e}")
        return jsonify({"error": "Failed to create file or folder"}), 500

# REST API endpoint to read a directory or file


@api.route("/api/read", methods=["GET"])
def read():
    """Read the contents of a directory or file."""
    try:
        fs_name = request.args.get("fs_name")
        path = request.args.get("path", "/")

        logger.info(f"Read request received: fs_name={fs_name}, path={path}")

        fs = app._adapters.get(fs_name)
        if not fs:
            logger.error(f"File system '{fs_name}' not found")
            return jsonify({"error": f"File system '{fs_name}' not found"}), 404

        # Check if path is a file or directory
        if fs.isfile(path):
            # Read and return file content
            try:
                content = fs.readtext(path)
                return jsonify({
                    "type": "file",
                    "path": path,
                    "content": content
                }), 200
            except UnicodeDecodeError:
                # If the file is not text-based (binary file)
                return jsonify({
                    "error": "File is not readable as text"
                }), 400
        elif fs.isdir(path):
            # List directory contents
            contents = fs.listdir(path)
            return jsonify({
                "type": "directory",
                "path": path,
                "contents": contents
            }), 200
        else:
            logger.error(f"Path '{path}' does not exist")
            return jsonify({"error": f"Path '{path}' does not exist"}), 404

    except Exception as e:
        logger.error(f"Error reading path: {e}")
        return jsonify({"error": "Failed to read path"}), 500

# REST API endpoint to update (save content to a file)


@api.route("/api/update", methods=["PUT"])
def update():
    """Save content to a file."""
    try:
        payload = request.json
        fs_name = payload.get("fs_name")
        path = payload.get("path")
        content = payload.get("content")

        logger.info(f"Update request received: fs_name={fs_name}, path={path}")

        if not fs_name or not path or content is None:
            return jsonify({"error": "fs_name, path, and content are required"}), 400

        result = app.save_content(fs_name=fs_name, path=path, content=content)

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error saving content to file: {e}")
        return jsonify({"error": "Failed to save content to file"}), 500

# REST API endpoint to rename a file or folder


@api.route("/api/rename", methods=["PATCH"])
def rename():
    """Rename a file or folder."""
    try:
        payload = request.json
        fs_name = payload.get("fs_name")
        old_path = payload.get("old_path")
        new_path = payload.get("new_path")

        logger.info(
            f"Rename request received: fs_name={fs_name}, old_path={old_path}, new_path={new_path}"
        )

        fs = app._adapters.get(fs_name)
        if not fs:
            logger.error(f"File system '{fs_name}' not found")
            return jsonify({"error": f"File system '{fs_name}' not found"}), 404

        # Check if the old_path is a file or a folder
        if fs.isdir(old_path):
            logger.info(f"Renaming folder: {old_path} -> {new_path}")
            fs.movedir(old_path, new_path, create=True)
        elif fs.isfile(old_path):
            logger.info(f"Renaming file: {old_path} -> {new_path}")
            fs.move(old_path, new_path)
        else:
            logger.error(f"Path '{old_path}' does not exist")
            return jsonify({"error": f"Path '{old_path}' does not exist"}), 404

        return jsonify({"message": "Renamed successfully"}), 200
    except Exception as e:
        logger.error(f"Error renaming file or folder: {e}")
        return jsonify({"error": "Failed to rename file or folder"}), 500

# REST API endpoint to delete a file or folder


@api.route("/api/delete", methods=["DELETE"])
def delete():
    """Delete a file or folder."""
    try:
        fs_name = request.args.get("fs_name")
        path = request.args.get("path")

        logger.info(f"Delete request received: fs_name={fs_name}, path={path}")

        if not fs_name or not path:
            return jsonify({"error": "fs_name and path are required"}), 400

        result = app.delete_item(fs_name=fs_name, path=path)

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error deleting file or folder: {e}")
        return jsonify({"error": "Failed to delete file or folder"}), 500

# REST API endpoint to download a file


@api.route("/api/download", methods=["GET"])
def download():
    """Download a file."""
    try:
        fs_name = request.args.get("fs_name")
        path = request.args.get("path")

        logger.info(
            f"Download request received: fs_name={fs_name}, path={path}")

        if not fs_name or not path:
            return jsonify({"error": "fs_name and path are required"}), 400

        result = app.download_file(fs_name=fs_name, path=path)

        if "error" in result:
            return jsonify(result), 500

        # Return file content as attachment
        return Response(
            result["content"],
            mimetype=result["mime_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{result["name"]}"',
                "Content-Length": result["size"]
            }
        )

    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({"error": "Failed to download file"}), 500

# REST API endpoint to upload a file


@api.route("/api/upload", methods=["POST"])
def upload():
    """Upload a file."""
    try:
        fs_name = request.form.get("fs_name")
        path = request.form.get("path", "/")

        if not fs_name:
            return jsonify({"error": "fs_name is required"}), 400

        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        content = file.read()
        result = app.upload_file(
            fs_name=fs_name,
            path=path,
            file_name=file.filename,
            content=content
        )

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result), 201

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({"error": "Failed to upload file"}), 500


# Expose app and api instances for Uvicorn
app_instance = WSGIMiddleware(app)
api_instance = WSGIMiddleware(api)

if __name__ == "__main__":
    # Use Waitress to serve the application (if needed)
    logger.info("Starting Waitress server on http://127.0.0.1:8006")
    serve(api_instance, host="127.0.0.1", port=8006)
    logger.info("Starting Flask API server on http://127.0.0.1:8005")
    serve(app_instance, host="127.0.0.1", port=8005)
