# VueFinder Backend API Documentation

This document provides detailed information about the available API endpoints in the VueFinder backend application.

## Authentication

All API requests require an API key to be sent in the request headers.

```
x-api-key: your-api-key
```

## Endpoints

### List File Systems

Lists all available file systems in the VueFinder application.

- **URL**: `/api/list_fs`
- **Method**: `GET`
- **Headers**:
  - `x-api-key`: API key (required)

#### Response

```json
{
  "file_systems": ["virtual_directory", "media", "media_rw"]
}
```

### Create File or Folder

Creates a new file or folder in the specified file system.

- **URL**: `/api/create`
- **Method**: `POST`
- **Headers**:
  - `Content-Type`: application/json
  - `x-api-key`: API key (required)
- **Payload**:

```json
{
  "fs_name": "media_rw",
  "path": "new_folder",
  "is_folder": true
}
```

#### Response

```json
{
  "message": "Folder created successfully",
  "path": "new_folder"
}
```

### Read Directory or File

Reads the contents of a directory or file.

- **URL**: `/api/read`
- **Method**: `GET`
- **Headers**:
  - `x-api-key`: API key (required)
- **Query Parameters**:
  - `fs_name`: Name of the file system
  - `path`: Path to the directory or file (defaults to "/")

#### Response for Directory

```json
{
  "type": "directory",
  "path": "/",
  "contents": ["file1.txt", "folder1", "image.jpg"]
}
```

#### Response for File

```json
{
  "type": "file",
  "path": "example.txt",
  "content": "File content here..."
}
```

### Update File Content

Updates the content of a file.

- **URL**: `/api/update`
- **Method**: `POST`
- **Headers**:
  - `Content-Type`: application/json
  - `x-api-key`: API key (required)
- **Payload**:

```json
{
  "fs_name": "media_rw",
  "path": "example.txt",
  "content": "New content for the file"
}
```

#### Response

```json
{
  "message": "Content saved successfully",
  "path": "example.txt"
}
```

### Rename File or Folder

Renames a file or folder.

- **URL**: `/api/rename`
- **Method**: `POST`
- **Headers**:
  - `Content-Type`: application/json
  - `x-api-key`: API key (required)
- **Payload**:

```json
{
  "fs_name": "media_rw",
  "old_path": "old_name.txt",
  "new_path": "new_name.txt"
}
```

#### Response

```json
{
  "message": "Renamed successfully"
}
```

### Delete File or Folder

Deletes a file or folder.

- **URL**: `/api/delete`
- **Method**: `POST`
- **Headers**:
  - `Content-Type`: application/json
  - `x-api-key`: API key (required)
- **Payload**:

```json
{
  "fs_name": "media_rw",
  "path": "file_to_delete.txt"
}
```

#### Response

```json
{
  "message": "Deleted successfully",
  "path": "file_to_delete.txt"
}
```

## Error Responses

All endpoints may return the following error responses:

### Authentication Error (401)

```json
{
  "error": "Unauthorized: Invalid API Key"
}
```

### Not Found Error (404)

```json
{
  "error": "File system 'invalid_fs' not found"
}
```

or

```json
{
  "error": "Path 'invalid_path' does not exist"
}
```

### Server Error (500)

```json
{
  "error": "Failed to perform operation"
}
```

## Example Usage

### Using cURL

1. **List File Systems**:

```bash
curl -H "x-api-key: your-api-key" http://127.0.0.1:8006/api/list_fs
```

2. **Create a Folder**:

```bash
curl -X POST -H "Content-Type: application/json" -H "x-api-key: your-api-key" \
-d '{"fs_name": "media_rw", "path": "new_folder", "is_folder": true}' \
http://127.0.0.1:8006/api/create
```

3. **Read Directory Contents**:

```bash
curl -H "x-api-key: your-api-key" \
"http://127.0.0.1:8006/api/read?fs_name=media_rw&path=/"
```

4. **Update File Content**:

```bash
curl -X POST -H "Content-Type: application/json" -H "x-api-key: your-api-key" \
-d '{"fs_name": "media_rw", "path": "example.txt", "content": "New content"}' \
http://127.0.0.1:8006/api/update
```

5. **Rename a File**:

```bash
curl -X POST -H "Content-Type: application/json" -H "x-api-key: your-api-key" \
-d '{"fs_name": "media_rw", "old_path": "old.txt", "new_path": "new.txt"}' \
http://127.0.0.1:8006/api/rename
```

6. **Delete a File**:

```bash
curl -X POST -H "Content-Type: application/json" -H "x-api-key: your-api-key" \
-d '{"fs_name": "media_rw", "path": "file_to_delete.txt"}' \
http://127.0.0.1:8006/api/delete
```

## Notes

1. The `fs_name` parameter in requests must match one of the file systems defined in your `config.toml` file.
2. File paths should be relative to the root of the specified file system.
3. The API key must match the key defined in your `.env` file.
4. Read-only file systems (where `read_only = true` in `config.toml`) will not allow create, update, rename, or delete operations.
