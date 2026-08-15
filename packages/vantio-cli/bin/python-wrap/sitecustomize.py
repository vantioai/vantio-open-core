# Injected onto PYTHONPATH by `vantio run python …`.
# Optics (and Gate, when a paid key is present on SDK 3.0.9+) wrap urllib /
# http.client / requests / httpx / aiohttp / urllib3 / socket.connect / subprocess curl and wget for this interpreter. Missing SDK is a warning, not a crash.
import sys

try:
    from vantio._process_wrap import install_process_wrap

    install_process_wrap()
except ImportError:
    try:
        import atexit
        import os
        import uuid

        from vantio._http_observe import install, uninstall

        tid = os.environ.get("VANTIO_TRACE_ID") or str(uuid.uuid4())
        os.environ.setdefault("VANTIO_TRACE_ID", tid)
        install(tid)
        atexit.register(uninstall)
    except ImportError:
        sys.stderr.write(
            "[ ∅ VANTIO ] Python wrap needs vantio-agent-sdk on this interpreter.\n"
            "  pip install vantio-agent-sdk\n"
            "  Then: vantio run python agent.py\n"
        )
except Exception as exc:
    sys.stderr.write(
        f"[ ∅ VANTIO ] Python wrap did not install ({type(exc).__name__}); agent continues.\n"
    )
