# AAsplit

A lightweight travel budget splitter and calculator based on Python and Google Sheets.

## How It Works

1. Export your shared budget from Google Sheets as a CSV file
2. Place it in the `data/` directory
3. Run `python3 split.py`
4. Choose a settlement mode and see who owes whom

## CSV Format

### Required vs Ignored Columns

Your CSV only needs **three required columns** — any other columns are **silently ignored** by the script. This means you can keep extra columns like `date`, `item`, `category`, `notes`, etc. in your spreadsheet for your own bookkeeping without affecting the calculation.

| Column | Required? | Accepted Names | Format |
|--------|-----------|---------------|--------|
| Amount | **Required** | `amount` or `金额` | Number or `$`-prefixed number, negative for refunds (e.g. `100.50`, `$100.50`, `-$40.00`) |
| Payer | **Required** | `payer`, `payor`, or `支付人` | Name of the person who paid |
| Participants | **Required** | `participants`, `split between`, `shared by`, or `参与人` | Comma-separated names wrapped in double quotes (e.g. `"Alice, Bob, Charlie"`) |
| Any other column | Ignored | — | Anything — these columns are kept for your reference only |

### Example CSV

See [`data/example.csv`](data/example.csv) for a complete example. It includes extra columns (`date`, `item`, `category`, `notes`) that are ignored by the script:

```csv
date,item,amount,payer,participants,category,notes
2025-07-01,Airport taxi,$68.00,Alice,"Alice, Bob, Charlie",Transport,From airport to hotel
2025-07-01,Hotel check-in,$450.00,Bob,"Alice, Bob, Charlie",Accommodation,3 nights
2025-07-01,Dinner at steakhouse,$126.50,Alice,"Alice, Bob, Charlie",Food,Welcome dinner
2025-07-02,Museum tickets,$90.00,Charlie,"Alice, Bob, Charlie",Activity,National museum
2025-07-02,Lunch,$55.00,Bob,"Bob, Charlie",Food,Alice had solo plans
2025-07-02,Souvenir shop,$38.00,Alice,"Alice",Shopping,Personal purchase
2025-07-03,Rental car,$160.00,Charlie,"Alice, Bob, Charlie",Transport,Day trip
2025-07-03,Gas,-$22.00,Charlie,"Alice, Bob, Charlie",Transport,Refund from rental agency
2025-07-03,Farewell dinner,$97.80,Bob,"Alice, Bob, Charlie",Food,Last night dinner
```

> **Tip:** Only `amount`, `payer`, and `participants` matter to the script. Columns like `date`, `item`, `category`, and `notes` are completely ignored — feel free to add as many extra columns as you like.

## Settlement Modes

### Scenario

Using the example above, Alice, Bob, and Charlie go on a 3-day trip. After all expenses are tallied:

| Person | Total Paid | Net Balance |
|--------|-----------|-------------|
| Alice | $232.50 | -$128.93 |
| Bob | $602.80 | +$251.86 |
| Charlie | $228.00 | -$122.93 |

Alice and Charlie owe money; Bob is owed money. Note that not everyone participates in every bill (e.g. Alice skipped the lunch, the souvenir is personal), so each person's "total owed" depends on which bills they were part of. The two modes below differ in **how** they settle these debts.

### Mode 1: Individual Transfers

Settles between each pair independently. Every bill is resolved one by one — for each bill, non-payers owe the payer their share, and mutual debts between each pair are netted out.

```
Using the scenario above:
  Alice → Bob:     $117.77
  Alice → Charlie:  $11.17
  Charlie → Bob:   $134.10
  Total: 3 transfers
```

This mode shows exactly where each debt comes from, making it transparent and easy to verify. However, it may produce more transfers since each pair settles independently.

### Mode 2: Consolidated Transfers

Minimizes the number of transfers using a greedy algorithm. Instead of looking at individual bills, it calculates each person's **net balance** (total paid minus total owed) and matches debtors to creditors.

```
Using the scenario above:
  Alice → Bob:   $128.93
  Charlie → Bob: $122.93
  Total: 2 transfers
```

Consolidated mode reduced from 3 transfers to 2 by eliminating the Alice → Charlie transfer and adjusting the amounts so that everyone's net balance is still fully settled. With more people, the difference can be even more significant.

## Using Google Sheets

### Setting Up Your Spreadsheet

1. Create a Google Sheet with the required columns (`amount`, `payer`, `participants`) and any extra columns you need
2. Use **Insert → Drop-down** to create dropdown lists for the `payer` column so you can quickly select a name from a predefined list of trip members
3. Use **Insert → Drop-down** with multiple selection for the `participants` column — or simply type comma-separated names in double quotes

> **Note on Participants:** Google Sheets dropdowns work best for single-select (like `payer`). For `participants`, you can either type names manually (e.g. `Alice, Bob, Charlie`) or use a single-select dropdown and manually add extra names with commas. The script expects comma-separated names.

### Downloading as CSV

1. In Google Sheets, go to **File → Download → Comma-separated values (.csv)**
2. Move the downloaded `.csv` file into the `data/` directory
3. Run `python3 split.py`

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
