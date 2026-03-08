# AAsplit

A lightweight travel budget splitter and calculator based on Python and Google Sheets.

## How It Works

1. Export your shared budget from Google Sheets as a CSV file
2. Place it in the `data/` directory
3. Run `python3 split.py`
4. Choose a settlement mode and see who owes whom

## CSV Format

Your CSV must have these three columns (other columns are ignored):

| Column | Accepted Names | Format |
|--------|---------------|--------|
| Amount | `amount` or `金额` | Number or `$`-prefixed number, negative for refunds (e.g. `100.50`, `$100.50`, `-$40.00`) |
| Payer | `payer`, `payor`, or `支付人` | Name of the person who paid |
| Participants | `participants`, `split between`, `shared by`, or `参与人` | Comma-separated names wrapped in double quotes (e.g. `"Alice, Bob, Charlie"`) |

Example:

```csv
item,amount,payer,participants
Dinner,$120.00,Alice,"Alice, Bob, Charlie"
Gas,$45.50,Bob,"Alice, Bob"
```

## Settlement Modes

### Mode 1: Individual Transfers

Settles between each pair independently.

```
Example: A, B, C travel together.
A paid more for B -> B pays A.
B paid more for C -> C pays B.
Each pair settles independently.
```

### Mode 2: Consolidated Transfers

Minimizes the number of transfers using a greedy algorithm.

```
Example: A, B, C travel together.
A is owed the most, B is owed a little, C owes the most.
C pays A $80, C pays B $20. A and B don't need to transfer.
Fewer transfers overall.
```

## Running Tests

```bash
python3 -m unittest test_split -v
```

49 test cases covering:
- Column name auto-detection (Chinese & English)
- Amount parsing and validation (including negative/refund amounts)
- Participants format validation
- CSV error handling
- Both settlement algorithms
- Algorithm invariants (no self-transfers, positive amounts, cross-mode balance consistency)
- Realistic scenarios (rounding, 5-person trips, refunds, hand-verified balances)

## Setup

```bash
git clone https://github.com/guanyu-gerry-tao/AAsplit-gadget.git
cd AAsplit-gadget
# Place your CSV in data/
python3 split.py
```

No external dependencies required — uses only Python standard library.
