import logging
from vuefinder import VuefinderApp, fill_fs
from fs.memoryfs import MemoryFS
from fs.wrap import WrapReadOnly
from fs.osfs import OSFS
from waitress import serve  # Import Waitress WSGI server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("waitress")

if __name__ == "__main__":
    m1 = MemoryFS()
    fill_fs(
        m1,
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
    app.add_fs("local", m1)
    app.add_fs("media", WrapReadOnly(OSFS("./tests/media")))
    app.add_fs("media-rw", OSFS("./tests/media"))

    # Use Waitress to serve the application
    logger.info("Starting Waitress server on http://127.0.0.1:8005")
    serve(app, host="127.0.0.1", port=8005)
