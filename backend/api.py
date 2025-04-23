from flask import Flask, jsonify, request
from fs.memoryfs import MemoryFS
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Initialize Flask app
app = Flask(__name__)

logging.basicConfig(level=logging.WARNING)

# Define the API key
REST_API_KEY = os.getenv("REST_API_KEY", "")
if not REST_API_KEY:
    logging.warning("REST_API_KEY is not set. Defaulting to an empty string.")

# Middleware to check API key


@app.before_request
def check_api_key():
    # Default to empty string if header is missing
    api_key = request.headers.get("REST-API-KEY", "")
    if api_key != REST_API_KEY:
        abort(403, description="Forbidden: Invalid API Key")


# Initialize an in-memory filesystem
m1 = MemoryFS()
m1.makedir("foo", recreate=True)  # Ensure the directory exists
with m1.open("foo/file.txt", "wb") as f:
    f.write(b"Hello World!")
with m1.open("foo/foo.txt", "wb") as f:
    f.write(b"foo bar baz")
m1.makedir("foobar", recreate=True)  # Ensure the directory exists
with m1.open("foobar/hello.txt", "wb") as f:
    f.write(b"Hello!")

# API Endpoints


@app.route('/api/hello', methods=['GET'])
def hello_world():
    return jsonify({"message": "Connection with File Browser API successful!"})


@app.route('/api/list', methods=['GET'])
def list_files():
    path = request.args.get("path", "/")  # Default to root directory
    if not m1.exists(path):
        return jsonify({"error": "Path does not exist"}), 404
    if not m1.isdir(path):
        return jsonify({"error": "Path is not a directory"}), 400
    files = list(m1.listdir(path))
    return jsonify({"files": files})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8006, debug=True)
