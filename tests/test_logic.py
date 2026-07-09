#!/usr/bin/env python3
"""claude-usage-peek 纯逻辑单测 — 零依赖(标准库 unittest), 不联网。

只测不碰网络/文件系统的纯函数: 解析 /api/oauth/usage、时间/数字格式化、
热力图分级、token 求和等。跑法:
  python3 -m unittest discover -s tests
  或  python3 tests/test_logic.py
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard  # noqa: E402
import quota      # noqa: E402
import usage      # noqa: E402

# /api/oauth/usage 的真实响应形状(截取关键字段)
SAMPLE_USAGE = {
    "five_hour": {"utilization": 27.0, "resets_at": "2026-07-09T10:29:59+00:00"},
    "seven_day": {"utilization": 9.0, "resets_at": "2026-07-15T04:59:59+00:00"},
    "limits": [
        {"kind": "session", "percent": 27, "severity": "normal", "scope": None},
        {"kind": "weekly_all", "percent": 9, "severity": "normal", "scope": None},
        {"kind": "weekly_scoped", "percent": 13, "severity": "normal",
         "resets_at": "2026-07-15T04:59:59+00:00",
         "scope": {"model": {"id": None, "display_name": "Fable"}, "surface": None}},
    ],
}


class TestScopedParse(unittest.TestCase):
    def test_fable(self):
        r = quota._scoped_from(SAMPLE_USAGE)
        self.assertIsNotNone(r)
        self.assertEqual(r["label"], "Fable")
        self.assertEqual(r["utilization"], 13.0)
        self.assertIsInstance(r["resetAt"], int)

    def test_label_follows_api(self):
        # 改名场景: display_name 变了, 解析出的 label 就跟着变
        data = {"limits": [{"kind": "weekly_scoped", "percent": 5,
                            "scope": {"model": {"display_name": "Sonnet"}}}]}
        self.assertEqual(quota._scoped_from(data)["label"], "Sonnet")

    def test_none_when_absent(self):
        self.assertIsNone(quota._scoped_from({"limits": [{"kind": "session", "percent": 5}]}))
        self.assertIsNone(quota._scoped_from({}))
        self.assertIsNone(quota._scoped_from({"limits": None}))

    def test_skip_when_percent_missing(self):
        data = {"limits": [{"kind": "weekly_scoped", "percent": None,
                            "scope": {"model": {"display_name": "X"}}}]}
        self.assertIsNone(quota._scoped_from(data))


class TestIsoToEpoch(unittest.TestCase):
    def test_valid(self):
        expected = int(datetime.datetime(2026, 7, 15, 4, 59, 59,
                                         tzinfo=datetime.timezone.utc).timestamp())
        self.assertEqual(quota._iso_to_epoch("2026-07-15T04:59:59+00:00"), expected)
        self.assertEqual(quota._iso_to_epoch("2026-07-15T04:59:59Z"), expected)

    def test_bad_inputs(self):
        self.assertIsNone(quota._iso_to_epoch(None))
        self.assertIsNone(quota._iso_to_epoch(""))
        self.assertIsNone(quota._iso_to_epoch("not a date"))


class TestHumanize(unittest.TestCase):
    def test(self):
        self.assertEqual(usage._humanize(0), "0")
        self.assertEqual(usage._humanize(999), "999")
        self.assertEqual(usage._humanize(1234), "1.2k")
        self.assertEqual(usage._humanize(2000), "2k")
        self.assertEqual(usage._humanize(8_400_000), "8.4M")
        self.assertEqual(usage._humanize(5_000_000), "5M")


class TestMsgTotal(unittest.TestCase):
    def test_sums_all_including_cache(self):
        u = {"input_tokens": 10, "output_tokens": 5,
             "cache_creation_input_tokens": 2, "cache_read_input_tokens": 3}
        self.assertEqual(usage._msg_total(u), 20)

    def test_missing_fields_default_zero(self):
        self.assertEqual(usage._msg_total({"input_tokens": 7}), 7)
        self.assertEqual(usage._msg_total({}), 0)


class TestFmtDur(unittest.TestCase):
    def _dur(self, **kw):
        return datetime.timedelta(**kw)

    def test_languages(self):
        try:
            dashboard.LANG = "en"
            self.assertEqual(dashboard._fmt_dur(self._dur(hours=2, minutes=18)), "2h 18m")
            self.assertEqual(dashboard._fmt_dur(self._dur(days=1, hours=3)), "1d 3h")
            self.assertEqual(dashboard._fmt_dur(self._dur(minutes=12)), "12m")
            dashboard.LANG = "zh"
            self.assertEqual(dashboard._fmt_dur(self._dur(hours=2, minutes=18)), "2小时18分")
            dashboard.LANG = "ja"
            self.assertEqual(dashboard._fmt_dur(self._dur(hours=2, minutes=18)), "2時間18分")
        finally:
            dashboard.LANG = "en"


class TestLevelFn(unittest.TestCase):
    def test_no_usage(self):
        lvl = dashboard._level_fn([0, 0, 0])
        self.assertEqual(lvl(0), 0)
        self.assertEqual(lvl(123), 0)

    def test_scale(self):
        lvl = dashboard._level_fn([10, 100, 1000])
        self.assertEqual(lvl(0), 0)          # 无用量 = 0 档
        self.assertEqual(lvl(1000), 4)       # 最大 = 最深
        for v in (10, 100, 1000):
            self.assertIn(lvl(v), (1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main(verbosity=2)
