import unittest

from usage_bridge import parse_rate_limits


class ParseRateLimitsTests(unittest.TestCase):
    def test_selects_codex_bucket(self):
        result = {
            "rateLimitsByLimitId": {
                "other": {"primary": {"usedPercent": 99}},
                "codex": {
                    "limitId": "codex",
                    "primary": {"usedPercent": 35, "windowDurationMins": 300, "resetsAt": "2026-10-31T18:30:00+08:00"},
                    "secondary": {"usedPercent": 62, "windowDurationMins": 10080, "resetsAt": "2026-11-02T08:00:00+08:00"},
                },
            }
        }
        parsed = parse_rate_limits(result)
        self.assertEqual(parsed["primary"]["used_percent"], 35)
        self.assertEqual(parsed["secondary"]["used_percent"], 62)

    def test_rejects_empty_usage(self):
        with self.assertRaises(ValueError):
            parse_rate_limits({"rateLimits": {"limitId": "codex"}})


if __name__ == "__main__":
    unittest.main()
