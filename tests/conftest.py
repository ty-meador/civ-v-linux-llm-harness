"""The suite never reaches a live game.

Every test plays against a fake, but the MCP path still takes the per-socket action lock (harness/action_lock.py),
and its key is the tuner socket's path. With the machine's own path that is the lock a live session holds: two
LeaderScreenGuard tests answered "another game operation is running (your own load_save, pid ...)" whenever the
suite ran during a live load or a turn finish, and a test holding the lock made a live call wait. So the socket
path is a scratch one for the whole run, set here before any `harness` module reads the environment
(`harness.client.DEFAULT_SOCK` is read at import). A test that names a socket of its own still does.
"""
import os
import tempfile

_scratch = tempfile.mkdtemp(prefix="civ5-tests-")
LIVE_SOCK = os.environ.get("CIV5_TUNERD_SOCK") or os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "civ5-tuner.sock")
os.environ["CIV5_TUNERD_SOCK"] = os.path.join(_scratch, "no-game.sock")
