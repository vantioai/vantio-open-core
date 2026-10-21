import unittest

from vantio._http_observe import _program_label


class ProgramLabelTest(unittest.TestCase):
    def test_script_basename(self) -> None:
        self.assertEqual(
            _program_label(["python", "/tmp/secret/agent.py", "--token", "nope"]),
            "agent.py",
        )

    def test_skips_flags(self) -> None:
        self.assertEqual(_program_label(["/usr/bin/python3", "-m", "agent"]), "agent")

    def test_eval_source_is_not_the_program_name(self) -> None:
        self.assertEqual(_program_label(["python", "-c", "print('secret')"]), "python")


if __name__ == "__main__":
    unittest.main()
