import unittest
from unittest.mock import patch
import bot


class BotTests(unittest.TestCase):
    def setUp(self):
        bot.SESSIONS.clear()

    def post(self, chat_id, text):
        bot.handle_message({'chat': {'id': chat_id, 'type': 'private'}, 'text': text})

    def test_handle_validation(self):
        self.assertEqual(bot.valid_handle('@Alaadin32'), '@Alaadin32')
        self.assertEqual(bot.valid_handle('Alaadin32'), '@Alaadin32')
        self.assertIsNone(bot.valid_handle('https://x.com/name'))
        self.assertIsNone(bot.valid_handle('a' * 16))

    @patch.object(bot, 'send')
    def test_four_buttons_immediate_exact_output(self, send):
        self.post(1, '/start')
        self.post(1, '@Alaadin32')
        self.assertEqual(send.call_args.args[2], ['تهمة التزييف', 'تهمة حسابات غير موثوقة', 'تهمة حقوق النشر', 'سبب اخر'])
        for label, reason in bot.CHOICES.items():
            before = send.call_count
            self.post(1, label)
            self.assertEqual(send.call_count, before + 1)
            self.assertEqual(send.call_args.args[1], bot.TEMPLATES[reason].replace('username', 'Alaadin32'))
        self.assertEqual(send.call_args.args[1], bot.TEMPLATES['other'])

    @patch.object(bot, 'send')
    def test_separate_users_and_reset(self, send):
        for chat, name in [(1, 'first'), (2, '@second')]:
            self.post(chat, '/start')
            self.post(chat, name)
        self.post(1, 'تهمة حسابات غير موثوقة')
        self.assertIn('@first', send.call_args.args[1])
        self.post(2, 'تهمة حقوق النشر')
        self.assertIn('@second', send.call_args.args[1])
        self.post(1, '/start')
        self.post(1, '@third')
        self.post(1, 'تهمة التزييف')
        self.assertIn('[third@]', send.call_args.args[1])
        self.assertNotIn('first', send.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
