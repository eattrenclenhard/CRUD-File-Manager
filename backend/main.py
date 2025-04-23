import logging
import os
import toml
from vuefinder import VuefinderApp, fill_fs
from fs.memoryfs import MemoryFS
from fs.wrap import WrapReadOnly
from fs.osfs import OSFS
from waitress import serve
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("waitress")


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

    app.add_fs("virtual_directory", virtual)

    config = load_config()

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

    logger.info("Starting Waitress server on http://127.0.0.1:8005")
    serve(app, host="127.0.0.1", port=8005)
