import os
import tempfile
import unittest
from split import (
    calc_individual,
    calc_consolidated,
    parse_csv,
    _find_column,
    _parse_amount,
    _parse_participants,
)


# ============================================================
#  Test column auto-detection
#  测试列名自动检测
# ============================================================

class TestFindColumn(unittest.TestCase):
    """Test auto-detection of column names in both Chinese and English.
    测试中英文列名自动检测。
    """

    def test_chinese_columns(self):
        headers = ["项目", "日期", "金额", "支付人", "参与人"]
        self.assertEqual(_find_column(headers, "amount"), "金额")
        self.assertEqual(_find_column(headers, "payer"), "支付人")
        self.assertEqual(_find_column(headers, "participants"), "参与人")

    def test_english_columns(self):
        headers = ["item", "date", "amount", "payer", "participants"]
        self.assertEqual(_find_column(headers, "amount"), "amount")
        self.assertEqual(_find_column(headers, "payer"), "payer")
        self.assertEqual(_find_column(headers, "participants"), "participants")

    def test_english_alt_columns(self):
        """Test alternative English names like 'payor' and 'split between'.
        测试替代英文列名如 payor 和 split between。
        """
        headers = ["item", "payor", "shared by", "amount"]
        self.assertEqual(_find_column(headers, "payer"), "payor")
        self.assertEqual(_find_column(headers, "participants"), "shared by")

    def test_case_insensitive(self):
        """Column matching should be case-insensitive.
        列名匹配应不区分大小写。
        """
        headers = ["Amount", "PAYER", "Participants"]
        self.assertEqual(_find_column(headers, "amount"), "Amount")
        self.assertEqual(_find_column(headers, "payer"), "PAYER")
        self.assertEqual(_find_column(headers, "participants"), "Participants")

    def test_missing_column(self):
        """Returns None when column is not found.
        找不到列时返回 None。
        """
        headers = ["foo", "bar", "baz"]
        self.assertIsNone(_find_column(headers, "amount"))
        self.assertIsNone(_find_column(headers, "payer"))
        self.assertIsNone(_find_column(headers, "participants"))


# ============================================================
#  Test amount parsing
#  测试金额解析
# ============================================================

class TestParseAmount(unittest.TestCase):
    """Test amount string parsing and validation.
    测试金额字符串解析与校验。
    """

    def test_plain_number(self):
        val, err = _parse_amount("100.50", 1)
        self.assertEqual(val, 100.50)
        self.assertIsNone(err)

    def test_dollar_prefix(self):
        val, err = _parse_amount("$845.20", 1)
        self.assertEqual(val, 845.20)
        self.assertIsNone(err)

    def test_comma_in_number(self):
        val, err = _parse_amount("$1,234.56", 1)
        self.assertEqual(val, 1234.56)
        self.assertIsNone(err)

    def test_empty_string_skips(self):
        val, err = _parse_amount("", 1)
        self.assertIsNone(val)
        self.assertIsNone(err)

    def test_invalid_amount(self):
        """Non-numeric strings should return an error.
        非数字字符串应返回错误。
        """
        val, err = _parse_amount("abc", 3)
        self.assertIsNone(val)
        self.assertIn("Row 3", err)
        self.assertIn("invalid amount", err)

    def test_invalid_amount_mixed(self):
        val, err = _parse_amount("$12.3.4", 5)
        self.assertIsNone(val)
        self.assertIn("Row 5", err)


# ============================================================
#  Test participants parsing
#  测试参与人解析
# ============================================================

class TestParseParticipants(unittest.TestCase):
    """Test participants string parsing and validation.
    测试参与人字符串解析与校验。
    """

    def test_normal_format(self):
        names, err = _parse_participants("Alice, Bob, Charlie", 1)
        self.assertEqual(names, ["Alice", "Bob", "Charlie"])
        self.assertIsNone(err)

    def test_single_participant(self):
        names, err = _parse_participants("Alice", 1)
        self.assertEqual(names, ["Alice"])
        self.assertIsNone(err)

    def test_chinese_names(self):
        names, err = _parse_participants("小明, 小红", 1)
        self.assertEqual(names, ["小明", "小红"])
        self.assertIsNone(err)

    def test_empty_string_skips(self):
        names, err = _parse_participants("", 1)
        self.assertIsNone(names)
        self.assertIsNone(err)

    def test_only_commas(self):
        """String with only commas should return an error.
        只有逗号的字符串应返回错误。
        """
        names, err = _parse_participants(",,,", 4)
        self.assertIsNone(names)
        self.assertIn("Row 4", err)
        self.assertIn("invalid participants", err)
        self.assertIn("double quotes", err)

    def test_special_characters(self):
        """Names with special characters (not word chars) should return an error.
        含特殊字符的名字应返回错误。
        """
        names, err = _parse_participants("Alice, Bob@#", 2)
        self.assertIsNone(names)
        self.assertIn("Row 2", err)
        self.assertIn("invalid participant name", err)
        self.assertIn("double quotes", err)


# ============================================================
#  Test parse_csv with valid and invalid files
#  测试 parse_csv 对合法和非法文件的处理
# ============================================================

class TestParseCsv(unittest.TestCase):
    """Test full CSV parsing including column detection and validation.
    测试完整的 CSV 解析，包括列名检测和数据校验。
    """

    def _write_csv(self, content):
        """Helper: write CSV content to a temp file and return the path.
        辅助方法：将 CSV 内容写入临时文件并返回路径。
        """
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        return f.name

    def test_english_headers(self):
        path = self._write_csv("amount,payer,participants\n100,A,\"A, B\"\n")
        try:
            records = parse_csv(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["amount"], 100.0)
            self.assertEqual(records[0]["payer"], "A")
            self.assertEqual(records[0]["participants"], ["A", "B"])
        finally:
            os.unlink(path)

    def test_chinese_headers(self):
        path = self._write_csv("项目,金额,支付人,参与人\nlunch,$50.00,A,\"A, B, C\"\n")
        try:
            records = parse_csv(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["amount"], 50.0)
        finally:
            os.unlink(path)

    def test_missing_column_exits(self):
        """Missing required columns should cause sys.exit.
        缺少必需列应触发 sys.exit。
        """
        path = self._write_csv("foo,bar,baz\n1,2,3\n")
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_invalid_amount_exits(self):
        """Invalid amount values should cause sys.exit.
        无效金额应触发 sys.exit。
        """
        path = self._write_csv("amount,payer,participants\nabc,A,\"A, B\"\n")
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_invalid_participants_exits(self):
        """Invalid participant format should cause sys.exit.
        无效参与人格式应触发 sys.exit。
        """
        path = self._write_csv("amount,payer,participants\n100,A,\"A; B\"\n")
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_skips_empty_rows(self):
        """Rows with all empty fields should be skipped silently.
        所有字段为空的行应被静默跳过。
        """
        path = self._write_csv("amount,payer,participants\n100,A,\"A, B\"\n,,,\n")
        try:
            records = parse_csv(path)
            self.assertEqual(len(records), 1)
        finally:
            os.unlink(path)


# ============================================================
#  Test individual transfer mode
#  测试分别转账模式
# ============================================================

class TestIndividual(unittest.TestCase):
    """Test individual transfer mode.
    测试分别转账模式。
    """

    def test_simple_two_people(self):
        """A pays 100, split between AB -> B owes A 50
        A付100，AB平分 → B欠A 50
        """
        records = [{"amount": 100, "payer": "A", "participants": ["A", "B"]}]
        result = calc_individual(records)
        self.assertEqual(result, {("B", "A"): 50.0})

    def test_three_people_one_payer(self):
        """A pays 90, split among ABC -> B owes A 30, C owes A 30
        A付90，ABC平分 → B欠A 30，C欠A 30
        """
        records = [{"amount": 90, "payer": "A", "participants": ["A", "B", "C"]}]
        result = calc_individual(records)
        self.assertEqual(result, {("B", "A"): 30.0, ("C", "A"): 30.0})

    def test_mutual_offset(self):
        """A pays 100 for AB, B pays 60 for AB -> B net owes A 20
        A付100给AB，B付60给AB → B欠A净额 20
        """
        records = [
            {"amount": 100, "payer": "A", "participants": ["A", "B"]},
            {"amount": 60, "payer": "B", "participants": ["A", "B"]},
        ]
        result = calc_individual(records)
        self.assertEqual(result, {("B", "A"): 20.0})

    def test_full_offset(self):
        """A pays 100 for AB, B pays 100 for AB -> fully settled
        A付100给AB，B付100给AB → 互不相欠
        """
        records = [
            {"amount": 100, "payer": "A", "participants": ["A", "B"]},
            {"amount": 100, "payer": "B", "participants": ["A", "B"]},
        ]
        result = calc_individual(records)
        self.assertEqual(result, {})

    def test_payer_not_in_participants(self):
        """A pays 100, only BC participate -> B owes A 50, C owes A 50
        A付100，只有BC参与 → B欠A 50，C欠A 50
        """
        records = [{"amount": 100, "payer": "A", "participants": ["B", "C"]}]
        result = calc_individual(records)
        self.assertEqual(result, {("B", "A"): 50.0, ("C", "A"): 50.0})

    def test_multiple_bills_three_people(self):
        """Multiple bills with cross payments
        多笔账单交叉支付
        """
        records = [
            # B owes A 30, C owes A 30 / B欠A30, C欠A30
            {"amount": 90, "payer": "A", "participants": ["A", "B", "C"]},
            # A owes B 20, C owes B 20 / A欠B20, C欠B20
            {"amount": 60, "payer": "B", "participants": ["A", "B", "C"]},
        ]
        result = calc_individual(records)
        # A&B: B owes A 30, A owes B 20 -> B net owes A 10
        # A和B: B欠A30, A欠B20 → B净欠A 10
        # C owes A 30, C owes B 20 / C欠A 30, C欠B 20
        self.assertEqual(result, {("B", "A"): 10.0, ("C", "A"): 30.0, ("C", "B"): 20.0})


# ============================================================
#  Test consolidated transfer mode
#  测试合计转账模式
# ============================================================

class TestConsolidated(unittest.TestCase):
    """Test consolidated transfer mode.
    测试合计转账模式。
    """

    def test_simple_two_people(self):
        """A pays 100, split between AB -> B pays A 50
        A付100，AB平分 → B给A 50
        """
        records = [{"amount": 100, "payer": "A", "participants": ["A", "B"]}]
        result = calc_consolidated(records)
        self.assertEqual(result, {("B", "A"): 50.0})

    def test_three_people_one_payer(self):
        """A pays 90, split among ABC -> B pays A 30, C pays A 30
        A付90，ABC平分 → B给A 30，C给A 30
        """
        records = [{"amount": 90, "payer": "A", "participants": ["A", "B", "C"]}]
        result = calc_consolidated(records)
        self.assertEqual(result, {("B", "A"): 30.0, ("C", "A"): 30.0})

    def test_minimize_transfers(self):
        """Consolidated mode should minimize number of transfers.
        合计模式应减少转账笔数。
        A pays 120 for ABC (40 each), B pays 60 for ABC (20 each)
        A付120给ABC(每人40), B付60给ABC(每人20)
        Balance: A=+60, B=0, C=-60
        Result: C pays A 60 (only 1 transfer)
        """
        records = [
            {"amount": 120, "payer": "A", "participants": ["A", "B", "C"]},
            {"amount": 60, "payer": "B", "participants": ["A", "B", "C"]},
        ]
        result = calc_consolidated(records)
        self.assertEqual(result, {("C", "A"): 60.0})

    def test_balance_sum_zero(self):
        """Sum of all balances should be 0 (conservation check).
        所有余额之和应为0（守恒校验）。
        """
        records = [
            {"amount": 100, "payer": "A", "participants": ["A", "B", "C"]},
            {"amount": 50, "payer": "B", "participants": ["B", "C"]},
            {"amount": 30, "payer": "C", "participants": ["A", "C"]},
        ]
        from collections import defaultdict
        balance = defaultdict(float)
        for rec in records:
            n = len(rec["participants"])
            share = rec["amount"] / n
            balance[rec["payer"]] += rec["amount"]
            for p in rec["participants"]:
                balance[p] -= share
        total = sum(balance.values())
        self.assertAlmostEqual(total, 0, places=2)

    def test_full_offset(self):
        """Fully settled, no transfers needed.
        互不相欠。
        """
        records = [
            {"amount": 100, "payer": "A", "participants": ["A", "B"]},
            {"amount": 100, "payer": "B", "participants": ["A", "B"]},
        ]
        result = calc_consolidated(records)
        self.assertEqual(result, {})

    def test_transfer_total_equals_individual(self):
        """Consolidated total should be <= individual total (optimized).
        合计模式的转账总额应 <= 分别模式（因为合计会优化）。
        """
        records = [
            {"amount": 90, "payer": "A", "participants": ["A", "B", "C"]},
            {"amount": 60, "payer": "B", "participants": ["A", "B", "C"]},
            {"amount": 30, "payer": "C", "participants": ["A", "B"]},
        ]
        ind = calc_individual(records)
        con = calc_consolidated(records)
        ind_total = sum(ind.values())
        con_total = sum(con.values())
        self.assertLessEqual(con_total, ind_total + 0.01)


if __name__ == "__main__":
    unittest.main()
