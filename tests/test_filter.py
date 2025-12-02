import unittest

from twitch_cli.config import Filter

class FilterTests(unittest.TestCase):
    def test_none(self):
        assert Filter._match("foo", None) == None
        assert Filter._match(None, "bar") == None

    def test_str(self):
        assert Filter._match("foo", "foo") == True
        assert Filter._match("foo", "bar") == False
        assert Filter._match("foo", None) == None

    def test_int(self):
        assert Filter._match(7, "7") == True
        assert Filter._match(1, "7") == False
        assert Filter._match(2, None) == None

    def test_re(self):
        assert Filter._match("/b", "abc") == True
        assert Filter._match("/b", None) == None

        assert Filter._match("/^a", "abc") == True
        assert Filter._match("/^b", "abc") == False

        assert Filter._match("/c$", "abc") == True
        assert Filter._match("/b$", "abc") == False
