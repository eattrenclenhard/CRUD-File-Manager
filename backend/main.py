import logging
import os
import toml
import bcrypt
from flask import Flask, jsonify, request, Response, make_response
from flask_cors import CORS
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
import sqlite3
import jwt
import datetime

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
CORS(api, resources={
    r"/*": {
        "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "x-api-key"],
        "supports_credentials": True,
        "expose_headers": ["Content-Type", "Authorization"],
        "allow_credentials": True
    }
})

# Middleware to enforce API key requirement


@api.before_request
def require_api_key():
    # Skip API key check for OPTIONS requests and login endpoint
    if request.method == "OPTIONS" or request.path == "/api/login":
        return None

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


class AuthMiddleware:
    def __init__(self, app):
        self.app = app
        self.access_code_hash = self._load_access_code_hash()

    def _load_access_code_hash(self) -> str:
        """Load the hashed access code from the database"""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'users.db'))
        try:
            cur = conn.cursor()
            cur.execute('SELECT access_code FROM access LIMIT 1')
            row = cur.fetchone()
            if row:
                return row[0]
            logger.error("No access code found in database")
            return None
        except Exception as e:
            logger.error(f"Error loading access code from database: {e}")
            return None
        finally:
            conn.close()

    def verify_access(self, request: Request) -> bool:
        """Verify access using session token"""
        if request.method == "OPTIONS":
            return True

        # Handle preview requests (check token in query params)
        if request.args.get("q") == "preview":
            token = request.args.get("token")
            if token and bcrypt.checkpw(token.encode('utf-8'), self.access_code_hash.encode('utf-8')):
                return True

        # Get session token from cookie
        token = request.cookies.get('session_token')
        if not token:
            logger.debug("No session token found in request")
            return False

        try:
            # Verify the JWT token
            jwt.decode(token, os.getenv('SECRET_KEY', 'your-secret-key'), algorithms=["HS256"])
            logger.debug("Session token validated successfully")
            return True
        except jwt.InvalidTokenError:
            logger.warning("Invalid session token")
            return False

    def __call__(self, environ, start_response):
        request = Request(environ)
        is_authenticated = self.verify_access(request)

        # Enable/disable VuefinderApp based on authentication
        if is_authenticated:
            self.app.enable()
        else:
            self.app.disable()

        return self.app(environ, start_response)


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

# REST API endpoint to handle login requests


@api.route("/api/login", methods=["POST", "OPTIONS"])
def login():
    """Handle login requests"""
    if request.method == "OPTIONS":
        response = make_response()
        return response, 200

    try:
        payload = request.json
        access_code = payload.get("accessCode")

        if not access_code:
            return jsonify({"error": "Access code is required"}), 400

        # Get the stored hash from the database
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'users.db'))
        try:
            cur = conn.cursor()
            cur.execute('SELECT access_code FROM access LIMIT 1')
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Authentication failed"}), 401

            stored_hash = row[0]

            # Verify the access code
            if bcrypt.checkpw(access_code.encode('utf-8'), stored_hash.encode('utf-8')):
                # Create a session token
                session_token = jwt.encode(
                    {
                        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7),
                        'iat': datetime.datetime.utcnow(),
                    },
                    os.getenv('SECRET_KEY', 'your-secret-key'),
                    algorithm='HS256'
                )

                response = jsonify({
                    "success": True,
                    "message": "Login successful"
                })
                
                # Set secure cookie with session token
                response.set_cookie(
                    'session_token',
                    session_token,
                    httponly=True,
                    secure=True,
                    samesite='Strict',
                    max_age=7 * 24 * 60 * 60  # 7 days
                )
                
                return response, 200
            else:
                return jsonify({"error": "Invalid access code"}), 401

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": f"Login failed: {str(e)}"}), 500


# Expose app and api instances for Uvicorn
wsgi_app = AuthMiddleware(app)
app_instance = WSGIMiddleware(wsgi_app)  # Wrap for Uvicorn compatibility
api_instance = WSGIMiddleware(api)

if __name__ == "__main__":
    # Use Waitress to serve the application (if needed)
    logger.info("Starting Waitress server on http://127.0.0.1:8006")
    serve(api_instance, host="127.0.0.1", port=8006)
    logger.info("Starting Flask API server on http://127.0.0.1:8005")
    serve(wsgi_app, host="127.0.0.1", port=8005)
