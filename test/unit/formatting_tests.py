#coding: utf-8
"""Unit tests for Bladerunner's output formatting."""


from __future__ import unicode_literals

import sys
from mock import patch

if sys.version_info <= (2, 7):
    import unittest2 as unittest
else:
    import unittest

if sys.version_info >= (3, 0):
    from io import StringIO
else:
    from StringIO import StringIO

from bladerunner import formatting


class TestFormatting(unittest.TestCase):
    def setUp(self):
        """Set up a StringIO capture on sys.stdout and a dummy result set."""

        self._stdout = sys.stdout
        sys.stdout = StringIO()

        self.result_set_a = [
            ("echo 'hello world'", "hello world"),
            ("cat dog", "cat: dog: No such file or directory"),
        ]
        self.result_set_b = [
            ("echo 'hello world'", "hello world"),
            ("cat cat", "cat: cat: No such file or directory")
        ]

        self.fake_results = [
            {"name": "server_a_1", "results": self.result_set_a},
            {"name": "server_a_2", "results": self.result_set_a},
            {"name": "server_a_3", "results": self.result_set_a},
            {"name": "server_a_4", "results": self.result_set_a},
            {"name": "server_b_1", "results": self.result_set_b},
            {"name": "server_b_2", "results": self.result_set_b},
            {"name": "server_b_3", "results": self.result_set_b},
            {
                "name": "server_c_1",
                "results": self.result_set_a + self.result_set_b,
            },
        ]

    def tearDown(self):
        """Reset stdout."""

        sys.stdout = self._stdout

    def test_no_empties(self):
        """No empties should return the same list without empty elements."""

        starting = ["something", "", "else", None, "and", "things", "", r""]
        self.assertEqual(
            formatting.no_empties(starting),
            ["something", "else", "and", "things"],
        )

    def test_format_output(self):
        """Should remove the first, last, and any line with command in it."""

        command = "super duper secret command"
        fake_output = (
            "someshell# {0}\nlots of interesting\noutput n stuff\nsomeshell#"
        ).format(command)
        if sys.version_info >= (3, 0):
            fake_output = bytes(fake_output, "utf-8")
        self.assertEqual(
            formatting.format_output(fake_output, command),
            "lots of interesting\noutput n stuff",
        )

    def test_command_in_second_line(self):
        """Long commands and small terminals can lead to leakage."""

        command = (
            "super secret and long rediculous command that receives so many "
            "arguments it spills over into the next line"
        )
        fake_output = (
            "someshell# {0}\n{1}\nlots of interesting\noutput n stuff\n"
            "someshell#"
        ).format(command[:50], command[50:])
        if sys.version_info >= (3, 0):
            fake_output = bytes(fake_output, "utf-8")
        self.assertEqual(
            formatting.format_output(fake_output, command),
            "lots of interesting\noutput n stuff",
        )

    def test_unknown_returns_line(self):
        """Let it fail if the shell cant display it if we can't decode."""

        if sys.version_info >= (3, 0):
            starting = bytes("Everybody loves a 🍔!", "utf-8")
        else:
            starting = "Everybody loves a 🍔!"

        output = formatting.format_line(starting)
        if sys.version_info >= (3, 0):
            # py3 will correctly decode and return a str vs the bytes input
            self.assertIn("Everybody loves a", output)
        else:
            self.assertEqual(output, starting)

    def test_consolidte_results(self):
        """Consolidate should merge matching server result sets."""

        expected_groups = [
            ["server_a_1", "server_a_2", "server_a_3", "server_a_4"],
            ["server_b_1", "server_b_2", "server_b_3"],
            ["server_c_1"],
        ]

        for result_set in formatting.consolidate(self.fake_results):
            self.assertIn("names", result_set)
            self.assertIsInstance(result_set["names"], list)
            self.assertNotIn("name", result_set)
            self.assertIn(result_set["names"], expected_groups)

    def test_csv_results(self):
        """Ensure CSV results print correctly."""

        formatting.csv_results(self.fake_results, {})
        stdout = sys.stdout.getvalue().strip()
        self.assertIn("server,command,result", stdout)
        for server in self.fake_results:
            self.assertIn(server["name"], stdout)
            for _, results in server["results"]:
                self.assertIn(results, stdout)

    def test_csv_custom_char(self):
        """Ensure you can specify the char used in csv_results."""

        options = {"csv_char": "@"}
        formatting.csv_results(self.fake_results, options)
        stdout = sys.stdout.getvalue().strip()
        self.assertIn("server@command@result", stdout)
        for server in self.fake_results:
            self.assertIn(server["name"], stdout)
            for _, results in server["results"]:
                self.assertIn(results, stdout)

    def test_csv_on_consolidated(self):
        """CSV results should still work post consolidation."""

        result_set = formatting.consolidate(self.fake_results)
        formatting.csv_results(result_set, {})
        stdout = sys.stdout.getvalue().strip()
        self.assertIn("server,command,result", stdout)
        for server in result_set:
            self.assertIn(" ".join(server["names"]), stdout)
            for _, results in server["results"]:
                self.assertIn(results, stdout)

    def test_prepare_results(self):
        """Ensure the results and options dicts are prepared for printing."""

        results, options = formatting.prepare_results(
            self.fake_results,
            {"width": 101},
        )

        self.assertEqual(options["left_len"], 10)
        self.assertIn("chars", options)
        self.assertEqual(options["style"], 0)
        self.assertEqual(options["width"], 101)
        self.assertIn("names", results[0])
        self.assertNotIn("name", results[0])

    def test_already_consildated(self):
        """Make sure we can consolidate before preparing."""

        results = formatting.consolidate(self.fake_results)
        with patch.object(formatting, "consolidate") as patched:
            formatting.prepare_results(results)

        self.assertFalse(patched.called)

    def test_minimum_left_len(self):
        """Left len should have a minimum of 6 chars."""

        for count, result_set in enumerate(self.fake_results):
            result_set["name"] = chr(97 + count)

        _, options = formatting.prepare_results(self.fake_results)
        self.assertEqual(options["left_len"], 6)

    def test_pretty_results(self):
        """Ensure pretty results is calling everything it should."""

        with patch.object(formatting, "pretty_header") as patched_header:
            with patch.object(formatting, "_pretty_result") as patched_result:
                with patch.object(formatting, "write") as patched_write:
                    formatting.pretty_results(self.fake_results)

        self.assertTrue(patched_header.called)
        self.assertTrue(patched_result.called)
        self.assertTrue(patched_write.called)

    def test_pretty_header(self):
        """Ensure proper formatting in the header line of pretty_output."""

        _, options = formatting.prepare_results(self.fake_results)
        formatting.pretty_header(options)
        stdout = sys.stdout.getvalue().strip()

        self.assertIn("Server", stdout)
        self.assertIn("Result", stdout)

    def test_header_with_jumphost(self):
        """The jumphost should appear in the header."""

        options = {"jump_host": "some_server"}
        _, options = formatting.prepare_results(self.fake_results, options)
        formatting.pretty_header(options)

        stdout = sys.stdout.getvalue().strip()

        self.assertIn("Server", stdout)
        self.assertIn("Result", stdout)
        self.assertIn("Jumpbox", stdout)
        self.assertIn("some_server", stdout)

    def test_pretty_result(self):
        """Ensure pretty results are correctly printed."""

        results, options = formatting.prepare_results(self.fake_results)

        formatting._pretty_result(results[0], options, results)

        stdout = sys.stdout.getvalue().strip()

        for server in results[0]["names"]:
            self.assertIn(server, stdout)
        for _, result in results[0]["results"]:
            self.assertIn(result, stdout)

    def test_bottom_up_in_first_result(self):
        """The first result when using a jumpbox should have a bot_up char."""

        results, options = formatting.prepare_results(
            self.fake_results,
            {"jump_host": "some_server"},
        )

        formatting._pretty_result(results[0], options, results)

        stdout = sys.stdout.getvalue().strip()

        for server in results[0]["names"]:
            self.assertIn(server, stdout)
        for _, result in results[0]["results"]:
            self.assertIn(result, stdout)

        self.assertIn(options["chars"]["bot_up"][options["style"]], stdout)

    def test_results_max_length(self):
        """Ensure the vertical alignment with multi line output commands."""

        fake_output = ["many", "lines", "of", "output"]
        self.fake_results.insert(
            0,
            {
                "name": "server_d_1",
                "results": [("obviously fake", "\n".join(fake_output))],
            }
        )
        results, options = formatting.prepare_results(
            self.fake_results,
            {"style": 1},
        )

        formatting._pretty_result(results[0], options, results)
        stdout = sys.stdout.getvalue().strip().splitlines()
        # self.fail(stdout)

        # top line should be a space separators
        self.assertIn(
            "{0}".format(options["chars"]["top"][options["style"]] * 10),
            stdout[0],
        )

        # then it should be the server name, separator and first line of cmd
        self.assertIn("server_d_1", stdout[1])
        self.assertIn(options["chars"]["side"][options["style"]], stdout[1])

        # then the multi line command should fill down the right column
        for line, fake_out in enumerate(fake_output, 1):
            self.assertIn(fake_out, stdout[line])

        # finally check total length
        self.assertEqual(len(stdout), 5)


if __name__ == "__main__":
    unittest.main()
