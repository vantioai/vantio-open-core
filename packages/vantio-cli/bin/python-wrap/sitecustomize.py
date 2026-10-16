# Injected onto PYTHONPATH by `vantio run python …`.
# When vantio-agent-sdk is installed, this records supported outbound calls
# for this interpreter. Missing SDK is a warning, not a crash.
# MCP awareness uses the same Node library as `vantio run node`. It does not
# replace the SDK and it does not listen.
import sys

try:
    import mcp_awareness

    mcp_awareness.install()
except Exception as exc:
    sys.stderr.write(
        f"[ ∅ VANTIO ] Python MCP awareness did not install ({type(exc).__name__}); agent continues.\n"
    )

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
