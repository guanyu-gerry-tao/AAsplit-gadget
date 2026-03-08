import csv
import os
import re
import sys
from collections import defaultdict

# Column name candidates: (field_key, [candidate names])
# 列名候选项：(字段key, [候选列名])
COLUMN_CANDIDATES = {
    "amount": ["amount", "金额"],
    "payer": ["payer", "payor", "支付人"],
    "participants": ["participants", "split between", "shared by", "参与人"],
}


def _find_column(headers, field_key):
    """Find matching column name from headers for a given field key (case-insensitive).
    根据字段key从表头中查找匹配的列名（不区分大小写）。
    """
    lower_headers = {h.lower().strip(): h for h in headers}
    for candidate in COLUMN_CANDIDATES[field_key]:
        if candidate.lower() in lower_headers:
            return lower_headers[candidate.lower()]
    return None


def _parse_amount(raw, row_num):
    """Parse amount string into float. Accepts plain numbers or $-prefixed numbers.
    解析金额字符串为浮点数。接受纯数字或$开头的数字。

    Returns (amount, error_message). error_message is None on success.
    """
    s = raw.strip()
    if not s:
        return None, None  # empty row, skip
    s = s.replace(",", "")
    # Handle $-prefix with optional leading sign: $100, -$100, +$100
    # 处理$前缀，支持可选的正负号：$100, -$100, +$100
    if s.startswith("$"):
        s = s[1:]
    elif s.startswith("-$") or s.startswith("+$"):
        s = s[0] + s[2:]
    try:
        val = float(s)
        return val, None
    except ValueError:
        return None, (
            f"Row {row_num}: invalid amount '{raw.strip()}'. "
            f"Expected a number or $-prefixed number (e.g. '100.50' or '$100.50')."
        )


def _parse_participants(raw, row_num):
    """Parse participants string into a list of names. Must be comma-separated names.
    解析参与人字符串为名字列表。必须是逗号分隔的名字格式。

    Returns (list, error_message). error_message is None on success.
    """
    s = raw.strip()
    if not s:
        return None, None  # empty row, skip
    # Validate format: comma-separated names like "A, B, C"
    # 验证格式：逗号分隔的名字，如 "A, B, C"
    parts = [p.strip() for p in s.split(",")]
    names = [p for p in parts if p]
    if not names:
        return None, (
            f"Row {row_num}: invalid participants '{s}'. "
            f"Expected comma-separated names wrapped in double quotes "
            f"(e.g. \"Alice, Bob, Charlie\")."
        )
    # Each name should be a simple word/phrase (letters, spaces, digits)
    # 每个名字应为简单字词（字母、空格、数字）
    for name in names:
        if not re.match(r'^[\w\s\u4e00-\u9fff]+$', name):
            return None, (
                f"Row {row_num}: invalid participant name '{name}'. "
                f"Expected comma-separated names wrapped in double quotes "
                f"(e.g. \"Alice, Bob, Charlie\")."
            )
    return names, None


def parse_csv(filepath):
    """Parse CSV file and return a list of bill records with amount, payer, participants.
    解析CSV文件，返回账单列表。每条账单包含 amount, payer, participants。

    Auto-detects column names by searching Chinese and English variants.
    自动检测列名，支持中英文。
    """
    records = []
    errors = []
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        # Auto-detect column names
        # 自动检测列名
        col_amount = _find_column(headers, "amount")
        col_payer = _find_column(headers, "payer")
        col_participants = _find_column(headers, "participants")

        missing = []
        if not col_amount:
            missing.append(
                "Amount column not found. "
                "Please add a column named 'amount' or '金额'."
            )
        if not col_payer:
            missing.append(
                "Payer column not found. "
                "Please add a column named 'payer' or '支付人'."
            )
        if not col_participants:
            missing.append(
                "Participants column not found. "
                "Please add a column named 'participants' or '参与人'. "
                "Values should be comma-separated names wrapped in double quotes "
                "(e.g. \"Alice, Bob, Charlie\")."
            )
        if missing:
            print(f"Error: missing required column(s) in '{os.path.basename(filepath)}':\n")
            for m in missing:
                print(f"  - {m}")
            print(f"\nFound columns: {headers}")
            sys.exit(1)

        for row_num, row in enumerate(reader, start=2):
            raw_amount = row[col_amount].strip()
            raw_payer = row[col_payer].strip()
            raw_participants = row[col_participants].strip()

            # Skip completely empty rows
            # 跳过完全空行
            if not raw_amount and not raw_payer and not raw_participants:
                continue

            amount, err = _parse_amount(raw_amount, row_num)
            if err:
                errors.append(err)
                continue
            if amount is None:
                continue

            if not raw_payer:
                errors.append(f"Row {row_num}: payer is empty.")
                continue

            participants, err = _parse_participants(raw_participants, row_num)
            if err:
                errors.append(err)
                continue
            if participants is None:
                continue

            records.append({
                "amount": amount,
                "payer": raw_payer,
                "participants": participants,
            })

    if errors:
        print(f"\nFound {len(errors)} error(s) while parsing '{os.path.basename(filepath)}':")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    return records


def calc_individual(records):
    """Mode 1: Individual transfers. Returns {(debtor, creditor): amount} net dict.
    模式1：分别转账。返回 {(debtor, creditor): amount} 的净额字典。

    For each bill, each non-payer participant owes the payer amount/n.
    For each pair (A, B), compute the net amount and keep only positive direction.
    对每笔账单，参与人中非支付人的每人欠支付人 amount/n。
    最后对每对 (A, B) 取净额，只保留净额 > 0 的方向。
    """
    # owes[A][B] = total amount A owes B
    # owes[A][B] = A 累计欠 B 的总额
    owes = defaultdict(lambda: defaultdict(float))
    for rec in records:
        n = len(rec["participants"])
        share = rec["amount"] / n
        payer = rec["payer"]
        for p in rec["participants"]:
            if p != payer:
                owes[p][payer] += share
    # Offset: net out A-owes-B against B-owes-A
    # 对冲：A欠B 和 B欠A 取净额
    result = {}
    all_people = set(owes.keys())
    for d in owes:
        all_people.update(owes[d].keys())
    for a in sorted(all_people):
        for b in sorted(all_people):
            if a >= b:
                continue
            net = owes[a][b] - owes[b][a]
            if abs(net) < 0.005:
                continue
            if net > 0:
                result[(a, b)] = round(net, 2)
            else:
                result[(b, a)] = round(-net, 2)
    return result


def calc_consolidated(records):
    """Mode 2: Consolidated transfers. Minimize the number of transfers.
    模式2：合计转账。最小化转账笔数。

    Compute each person's net balance (paid - owed), then use greedy matching.
    先算每人的净余额（支付 - 应付），然后用贪心算法配对。
    """
    balance = defaultdict(float)
    for rec in records:
        n = len(rec["participants"])
        share = rec["amount"] / n
        payer = rec["payer"]
        balance[payer] += rec["amount"]
        for p in rec["participants"]:
            balance[p] -= share

    # Split into debtors (balance < 0) and creditors (balance > 0)
    # 分成债务人（余额<0）和债权人（余额>0）
    debtors = []  # (name, amount owed) — positive
    creditors = []  # (name, amount to receive) — positive
    for person, bal in balance.items():
        if bal < -0.005:
            debtors.append([person, -bal])
        elif bal > 0.005:
            creditors.append([person, bal])

    # Sort descending by amount so larger amounts are matched first
    # 按金额降序排，让大额先配对
    debtors.sort(key=lambda x: -x[1])
    creditors.sort(key=lambda x: -x[1])

    result = {}
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor, d_amt = debtors[i]
        creditor, c_amt = creditors[j]
        transfer = min(d_amt, c_amt)
        if transfer > 0.005:
            result[(debtor, creditor)] = round(transfer, 2)
        debtors[i][1] -= transfer
        creditors[j][1] -= transfer
        if debtors[i][1] < 0.005:
            i += 1
        if creditors[j][1] < 0.005:
            j += 1

    return result


def print_results(result, mode_name):
    print(f"\n{'='*50}")
    print(f"  {mode_name}")
    print(f"{'='*50}")
    if not result:
        print("  No transfers needed, all settled!")
        return
    total = 0
    for (debtor, creditor), amount in sorted(result.items()):
        print(f"  {debtor} -> {creditor}:  ${amount:.2f}")
        total += amount
    print(f"{'='*50}")
    print(f"  {len(result)} transfer(s), total ${total:.2f}")


def select_csv():
    """List all CSV files in data/ sorted by modification time (newest first) and let user pick one.
    列出 data/ 目录下所有 CSV 文件，按修改时间降序排列，让用户选择。
    """
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.isdir(data_dir):
        print(f"Error: data directory not found at {data_dir}")
        sys.exit(1)
    csv_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".csv")]
    if not csv_files:
        print("Error: no CSV files found in data/")
        print("Please download your budget CSV file into the data/ directory.")
        print("The CSV should have columns for amount, payer, and participants.")
        sys.exit(1)
    # Sort by modification time, newest first
    # 按修改时间降序排列，最新的排第一
    csv_files.sort(key=lambda f: os.path.getmtime(os.path.join(data_dir, f)), reverse=True)
    if len(csv_files) == 1:
        print(f"Found 1 CSV file: {csv_files[0]}\n")
        return os.path.join(data_dir, csv_files[0])
    print("Available CSV files (sorted by latest modified):\n")
    for i, f in enumerate(csv_files, 1):
        print(f"  {i} - {f}")
    print()
    choice = input(f"Select a file (1-{len(csv_files)}): ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(csv_files):
            return os.path.join(data_dir, csv_files[idx])
    except ValueError:
        pass
    print("Invalid selection.")
    sys.exit(1)


def main():
    csv_path = select_csv()
    records = parse_csv(csv_path)

    print("Please select a mode:\n")
    print("  1 - Individual transfers (settle between each pair)")
    print("      Example: A, B, C travel together.")
    print("      A paid more for B -> B pays A.")
    print("      B paid more for C -> C pays B.")
    print("      Each pair settles independently.\n")
    print("  2 - Consolidated transfers (minimize number of transfers)")
    print("      Example: A, B, C travel together.")
    print("      A is owed the most, B is owed a little, C owes the most.")
    print("      C pays A $80, C pays B $20. A and B don't need to transfer.")
    print("      Fewer transfers overall.\n")
    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        result = calc_individual(records)
        print_results(result, "Individual Transfers")
    elif choice == "2":
        result = calc_consolidated(records)
        print_results(result, "Consolidated Transfers")
    else:
        print("Invalid input, please enter 1 or 2.")


if __name__ == "__main__":
    main()
