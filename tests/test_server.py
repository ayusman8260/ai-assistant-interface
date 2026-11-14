import os
import unittest
from datetime import datetime
from unittest import mock

import assistant
import server


class AssistantTests(unittest.TestCase):
    def test_math(self):
        self.assertIn("**1029**", assistant.reply("2^10 + 5"))
        self.assertIn("**28**", assistant.reply("what is 12 * (3 + 4) / 3"))
        self.assertIn("zero", assistant.reply("1/0"))

    def test_math_cannot_execute_code(self):
        for evil in ["__import__('os').system('echo hi')", "open('x')", "9**9**9"]:
            self.assertNotIn("hi", assistant.reply(evil).replace("this", ""))
        with self.assertRaises(ValueError):
            assistant.safe_eval("2**1000")

    def test_time_and_help(self):
        now = datetime(2026, 11, 14, 15, 30)
        self.assertIn("03:30 PM", assistant.reply("what time is it", now))
        self.assertIn("Saturday, 14 November 2026", assistant.reply("what is today's date", now))
        self.assertIn("offline mode", assistant.reply("help"))

    def test_code_block(self):
        self.assertIn("```python", assistant.reply("show me a python example"))


class ServerTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.c = server.create_app().test_client()

    def test_offline_chat(self):
        r = self.c.post("/api/chat", json={"messages": [{"role": "user", "content": "3+4"}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["mode"], "offline")

    def test_validation(self):
        bad = [None, [], [{"role": "system", "content": "x"}], [{"role": "assistant", "content": "x"}],
               [{"role": "user", "content": "  "}]]
        for messages in bad:
            self.assertEqual(self.c.post("/api/chat", json={"messages": messages}).status_code, 400)

    def test_api_mode_uses_key_and_handles_failure(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}):
            with mock.patch.object(server, "call_anthropic", return_value="from api") as m:
                r = self.c.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
                self.assertEqual(r.get_json()["reply"], "from api")
                self.assertEqual(m.call_args[0][1], "k")
            with mock.patch.object(server, "call_anthropic", side_effect=OSError("down")):
                r = self.c.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
                self.assertEqual(r.status_code, 502)
                self.assertIn("Could not reach", r.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
