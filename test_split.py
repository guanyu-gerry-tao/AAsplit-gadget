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

    def test_negative_plain(self):
        """Negative plain number (e.g. refund).
        负数纯数字（如退款）。
        """
        val, err = _parse_amount("-50.00", 1)
        self.assertEqual(val, -50.0)
        self.assertIsNone(err)

    def test_negative_dollar_prefix(self):
        """Negative with dollar sign: -$50.00
        带美元符号的负数：-$50.00
        """
        val, err = _parse_amount("-$50.00", 1)
        self.assertEqual(val, -50.0)
        self.assertIsNone(err)

    def test_dollar_negative(self):
        """Dollar sign then negative: $-50.00
        美元符号后跟负号：$-50.00
        """
        val, err = _parse_amount("$-50.00", 1)
        self.assertEqual(val, -50.0)
        self.assertIsNone(err)


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


# ============================================================
#  Test algorithm invariants (property-based checks)
#  测试算法不变量（属性校验）
# ============================================================

class TestInvariants(unittest.TestCase):
    """Verify mathematical invariants that must hold for ANY valid input.
    验证对任意合法输入都必须成立的数学不变量。
    """

    SAMPLE_RECORDS = [
        {"amount": 845.20, "payer": "A", "participants": ["A", "B", "C", "D", "E"]},
        {"amount": 980.40, "payer": "B", "participants": ["B", "C", "D"]},
        {"amount": 590.58, "payer": "B", "participants": ["A", "B", "C", "D", "E"]},
        {"amount": 163.40, "payer": "A", "participants": ["A", "E"]},
        {"amount": 459.54, "payer": "E", "participants": ["A", "B", "C", "D", "E"]},
        {"amount": 63.16, "payer": "A", "participants": ["D"]},
        {"amount": 102.23, "payer": "C", "participants": ["B", "C", "D"]},
        {"amount": 131.58, "payer": "D", "participants": ["A", "B", "C", "D", "E"]},
        {"amount": 112.00, "payer": "B", "participants": ["B", "D"]},
    ]

    def test_no_self_transfers(self):
        """No one should transfer money to themselves.
        不应出现给自己转账的情况。
        """
        ind = calc_individual(self.SAMPLE_RECORDS)
        con = calc_consolidated(self.SAMPLE_RECORDS)
        for (debtor, creditor) in ind:
            self.assertNotEqual(debtor, creditor, f"Self-transfer found: {debtor} -> {creditor}")
        for (debtor, creditor) in con:
            self.assertNotEqual(debtor, creditor, f"Self-transfer found: {debtor} -> {creditor}")

    def test_all_transfers_positive(self):
        """All transfer amounts must be > 0.
        所有转账金额必须大于 0。
        """
        ind = calc_individual(self.SAMPLE_RECORDS)
        con = calc_consolidated(self.SAMPLE_RECORDS)
        for (debtor, creditor), amount in ind.items():
            self.assertGreater(amount, 0, f"Non-positive transfer: {debtor} -> {creditor}: {amount}")
        for (debtor, creditor), amount in con.items():
            self.assertGreater(amount, 0, f"Non-positive transfer: {debtor} -> {creditor}: {amount}")

    def test_both_modes_same_net_balance(self):
        """Both modes must produce the same net balance per person.
        两种模式必须产生相同的每人净余额。
        This is the strongest correctness check.
        这是最强的正确性校验。
        """
        from collections import defaultdict
        ind = calc_individual(self.SAMPLE_RECORDS)
        con = calc_consolidated(self.SAMPLE_RECORDS)

        ind_net = defaultdict(float)
        for (debtor, creditor), amount in ind.items():
            ind_net[debtor] -= amount
            ind_net[creditor] += amount

        con_net = defaultdict(float)
        for (debtor, creditor), amount in con.items():
            con_net[debtor] -= amount
            con_net[creditor] += amount

        all_people = set(ind_net.keys()) | set(con_net.keys())
        for person in all_people:
            self.assertAlmostEqual(
                ind_net[person], con_net[person], places=1,
                msg=f"{person}: individual net={ind_net[person]:.2f}, consolidated net={con_net[person]:.2f}"
            )


# ============================================================
#  Test realistic edge cases
#  测试现实场景的边界情况
# ============================================================

class TestRealisticScenarios(unittest.TestCase):
    """Test edge cases that occur in real-world trip splitting.
    测试现实旅行分账中出现的边界情况。
    """

    def test_payer_pays_for_self_only(self):
        """A pays 100 for only themselves -> no transfers needed.
        A 付了 100 但只有自己参与 → 无需转账。
        E.g. someone's personal purchase got recorded by mistake.
        """
        records = [{"amount": 100, "payer": "A", "participants": ["A"]}]
        ind = calc_individual(records)
        con = calc_consolidated(records)
        self.assertEqual(ind, {})
        self.assertEqual(con, {})

    def test_uneven_split_rounding(self):
        """$100 split 3 ways = $33.33... each. Verify no money is lost to rounding.
        100 元三人分 = 每人 33.33... 验证精度不丢失。
        """
        records = [{"amount": 100, "payer": "A", "participants": ["A", "B", "C"]}]
        result = calc_individual(records)
        # B and C each owe A 33.33
        # B 和 C 各欠 A 33.33
        self.assertAlmostEqual(result[("B", "A")], 33.33, places=2)
        self.assertAlmostEqual(result[("C", "A")], 33.33, places=2)
        # Each transfer is rounded to 2 decimal places: round(100/3, 2) = 33.33
        # Total = 33.33 * 2 = 66.66 (rounding loss of $0.01 is acceptable)
        # 每笔转账四舍五入到分：round(100/3, 2) = 33.33，总计 66.66（损失 $0.01 可接受）
        total_owed = sum(result.values())
        self.assertAlmostEqual(total_owed, 66.66, places=2)

    def test_five_person_trip(self):
        """Simulate a realistic 5-person trip with mixed participation.
        模拟 5 人旅行，参与人数不同的多笔账单。
        """
        records = [
            # Hotel: all 5 split equally / 酒店：5 人平分
            {"amount": 500, "payer": "A", "participants": ["A", "B", "C", "D", "E"]},
            # Dinner: 3 people / 晚餐：3 人
            {"amount": 120, "payer": "B", "participants": ["A", "B", "C"]},
            # Tickets: 2 people / 门票：2 人
            {"amount": 80, "payer": "C", "participants": ["C", "D"]},
            # Uber: all 5 / 打车：5 人
            {"amount": 50, "payer": "D", "participants": ["A", "B", "C", "D", "E"]},
            # Gift: paid by E for A only / 礼物：E 付给 A
            {"amount": 30, "payer": "E", "participants": ["A"]},
        ]
        # Verify balance conservation for individual mode
        # 验证分别模式的余额守恒
        ind = calc_individual(records)
        # In individual mode, each person's net in/out should match consolidated
        # 分别模式下，每人的净收支应与合计模式一致

        # Verify balance conservation for consolidated mode
        # 验证合计模式的余额守恒
        from collections import defaultdict
        balance = defaultdict(float)
        for rec in records:
            n = len(rec["participants"])
            share = rec["amount"] / n
            balance[rec["payer"]] += rec["amount"]
            for p in rec["participants"]:
                balance[p] -= share
        self.assertAlmostEqual(sum(balance.values()), 0, places=2)

        con = calc_consolidated(records)
        # Consolidated transfers should fully settle all balances
        # 合计转账应完全清算所有余额
        settled = defaultdict(float)
        for (debtor, creditor), amount in con.items():
            settled[debtor] -= amount
            settled[creditor] += amount
        for person, bal in balance.items():
            self.assertAlmostEqual(settled[person], bal, places=2,
                msg=f"{person}: expected balance {bal:.2f}, got settled {settled[person]:.2f}")

    def test_consolidated_correctness(self):
        """Verify consolidated mode produces correct settlement, not just fewer transfers.
        验证合计模式结果的正确性，而不仅仅是转账笔数更少。
        A pays 300 for ABCD (75 each), B pays 100 for BCD (33.33 each)
        A 付 300 给 ABCD（每人 75），B 付 100 给 BCD（每人 33.33）
        """
        records = [
            {"amount": 300, "payer": "A", "participants": ["A", "B", "C", "D"]},
            {"amount": 100, "payer": "B", "participants": ["B", "C", "D"]},
        ]
        from collections import defaultdict
        # Calculate expected balances
        # 计算预期余额
        balance = defaultdict(float)
        for rec in records:
            n = len(rec["participants"])
            share = rec["amount"] / n
            balance[rec["payer"]] += rec["amount"]
            for p in rec["participants"]:
                balance[p] -= share

        con = calc_consolidated(records)
        # Verify transfers fully settle all balances
        # 验证转账完全清算所有余额
        settled = defaultdict(float)
        for (debtor, creditor), amount in con.items():
            settled[debtor] -= amount
            settled[creditor] += amount
        for person in balance:
            self.assertAlmostEqual(settled[person], balance[person], places=1)

    def test_one_person_pays_everything(self):
        """One person pays all bills — common in real trips.
        一个人付了所有账单 — 旅行中常见。
        """
        records = [
            {"amount": 200, "payer": "A", "participants": ["A", "B", "C"]},
            {"amount": 150, "payer": "A", "participants": ["A", "B"]},
            {"amount": 60, "payer": "A", "participants": ["A", "B", "C"]},
        ]
        ind = calc_individual(records)
        # B owes A: 200/3 + 150/2 + 60/3 = 66.67 + 75 + 20 = 161.67
        # C owes A: 200/3 + 60/3 = 66.67 + 20 = 86.67
        self.assertAlmostEqual(ind[("B", "A")], 161.67, places=2)
        self.assertAlmostEqual(ind[("C", "A")], 86.67, places=2)
        # No transfer between B and C
        # B 和 C 之间无转账
        self.assertNotIn(("B", "C"), ind)
        self.assertNotIn(("C", "B"), ind)


    def test_negative_amount_refund(self):
        """Negative amount acts as a refund: reduces what participants owe.
        负数金额视为退款：减少参与人的应付金额。
        A pays 100 for AB (each owes 50), then gets -40 refund for AB (each credited 20).
        A 付 100 给 AB（各 50），然后退款 -40 给 AB（各退 20）。
        Net: B owes A 50 - 20 = 30.
        """
        records = [
            {"amount": 100, "payer": "A", "participants": ["A", "B"]},
            {"amount": -40, "payer": "A", "participants": ["A", "B"]},
        ]
        ind = calc_individual(records)
        self.assertAlmostEqual(ind[("B", "A")], 30.0, places=2)
        con = calc_consolidated(records)
        self.assertAlmostEqual(con[("B", "A")], 30.0, places=2)

    def test_negative_amount_full_refund(self):
        """Full refund cancels the original bill completely.
        全额退款完全抵消原始账单。
        """
        records = [
            {"amount": 100, "payer": "A", "participants": ["A", "B"]},
            {"amount": -100, "payer": "A", "participants": ["A", "B"]},
        ]
        ind = calc_individual(records)
        self.assertEqual(ind, {})
        con = calc_consolidated(records)
        self.assertEqual(con, {})

    def test_real_trip_structure(self):
        """Simulate a realistic 5-person trip structure with varied groups.
        模拟真实的 5 人旅行结构：不同参与组合。
        Hand-verified expected results.
        """
        records = [
            # All 5 / 全员 5 人
            {"amount": 500, "payer": "Alex", "participants": ["Alex", "Blake", "Casey", "Dana", "Eli"]},
            # 3 people / 3 人
            {"amount": 300, "payer": "Blake", "participants": ["Blake", "Casey", "Dana"]},
            # 2 people / 2 人
            {"amount": 100, "payer": "Alex", "participants": ["Alex", "Eli"]},
            # Paid for someone else / 给别人付
            {"amount": 60, "payer": "Alex", "participants": ["Dana"]},
            # All 5 again / 再次全员
            {"amount": 250, "payer": "Eli", "participants": ["Alex", "Blake", "Casey", "Eli", "Dana"]},
        ]

        # Hand-calculate balances:
        # 手动计算余额：
        # Alex: paid 500+100+60=660, owes 500/5+100/2+250/5 = 100+50+50 = 200. Balance = +460
        # Blake: paid 300, owes 500/5+300/3+250/5 = 100+100+50 = 250. Balance = +50
        # Casey: paid 0, owes 500/5+300/3+250/5 = 100+100+50 = 250. Balance = -250
        # Dana: paid 0, owes 500/5+300/3+60+250/5 = 100+100+60+50 = 310. Balance = -310
        # Eli: paid 250, owes 500/5+100/2+250/5 = 100+50+50 = 200. Balance = +50
        # Sum: 460+50-250-310+50 = 0 ✓

        from collections import defaultdict
        balance = defaultdict(float)
        for rec in records:
            n = len(rec["participants"])
            share = rec["amount"] / n
            balance[rec["payer"]] += rec["amount"]
            for p in rec["participants"]:
                balance[p] -= share

        # Verify hand-calculated balances
        # 验证手动计算的余额
        self.assertAlmostEqual(balance["Alex"], 460, places=2)
        self.assertAlmostEqual(balance["Blake"], 50, places=2)
        self.assertAlmostEqual(balance["Casey"], -250, places=2)
        self.assertAlmostEqual(balance["Dana"], -310, places=2)
        self.assertAlmostEqual(balance["Eli"], 50, places=2)

        # Verify consolidated mode settles correctly
        # 验证合计模式正确清算
        con = calc_consolidated(records)
        settled = defaultdict(float)
        for (debtor, creditor), amount in con.items():
            settled[debtor] -= amount
            settled[creditor] += amount
        for person in balance:
            self.assertAlmostEqual(settled[person], balance[person], places=1,
                msg=f"{person}: expected {balance[person]:.2f}, got {settled[person]:.2f}")

        # Verify individual mode: total net flow per person matches balance
        # 验证分别模式：每人的净流入流出与余额一致
        ind = calc_individual(records)
        ind_settled = defaultdict(float)
        for (debtor, creditor), amount in ind.items():
            ind_settled[debtor] -= amount
            ind_settled[creditor] += amount
        for person in balance:
            self.assertAlmostEqual(ind_settled[person], balance[person], places=1,
                msg=f"Individual - {person}: expected {balance[person]:.2f}, got {ind_settled[person]:.2f}")


if __name__ == "__main__":
    unittest.main()
