import unittest
from unittest.mock import patch

import bot


class BotTests(unittest.TestCase):
    def setUp(self):
        bot.SESSIONS.clear()

    def test_handle_validation(self):
        self.assertEqual(bot.valid_handle("@Alaadin32"), "@Alaadin32")
        self.assertIsNone(bot.valid_handle("https://x.com/name"))
        self.assertIsNone(bot.valid_handle("a" * 16))

    @patch.object(bot, "send")
    def test_flow_and_clear(self, send):
        def post(value):
            bot.handle_message({"chat": {"id": 1, "type": "private"}, "text": value})
        post("/start")
        post("@Alaadin32")
        post("سبب غير معروف")
        post("وجدت الحساب موقوفًا اليوم ولا أعرف سبب الإيقاف.")
        self.assertNotIn(1, bot.SESSIONS)
        self.assertIn("@Alaadin32", send.call_args_list[-2].args[1])
        self.assertIn(bot.APPEAL_URL, send.call_args_list[-1].args[1])

    def test_copyright_draft_is_not_counter_notice(self):
        text = bot.draft("@account", "copyright", "I got a copyright notice.")
        self.assertIn("requesting clarification", text)
        self.assertNotIn("under penalty of perjury", text)


if __name__ == "__main__":
    unittest.main()
