"""tests/conftest.py: the suite's socket path, and so its action lock, is not the live game's."""
import fcntl
import os
import unittest

from conftest import LIVE_SOCK
from harness import client, mcp_server
from harness.action_lock import action_lock, lock_path


class SuiteSocket(unittest.TestCase):
    def test_the_server_under_test_names_a_scratch_socket_that_does_not_exist(self):
        self.assertNotEqual(mcp_server._sock(), LIVE_SOCK)
        self.assertEqual(client.DEFAULT_SOCK, mcp_server._sock())
        self.assertFalse(os.path.exists(mcp_server._sock()))

    def test_a_guarded_call_of_the_suite_goes_through_while_the_live_games_lock_is_held(self):
        """What failed before: a live load held the machine's lock and two guard tests were refused."""
        self.assertNotEqual(lock_path(mcp_server._sock()), lock_path(LIVE_SOCK))
        scratch_live = mcp_server._sock() + ".stands-for-live"       # never the real lock file: a live call would wait
        with lock_path(scratch_live).open("a+") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with action_lock(mcp_server._sock(), timeout=0.2, seat=0, tool="turn_status"):
                    pass
            finally:
                fcntl.flock(held, fcntl.LOCK_UN)
        lock_path(scratch_live).unlink(missing_ok=True)
        lock_path(mcp_server._sock()).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
