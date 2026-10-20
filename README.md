# splitCSV

A lightweight, zero-dependency Python CLI tool and module for splitting large CSV files into smaller chunks while preserving the first (header) row across every generated file.

## Features

- **Header Preservation**: Automatically repeats the first row of the input CSV at the top of every split file.
- **Exact Formatting Fidelity**: Preserves original delimiters (`,`, `;`, `\t`, etc.), quote styles, line endings (`\r\n` or `\n`), and character encodings byte-for-byte without re-serializing fields.
- **Multiline CSV Aware**: Properly parses quoted fields containing embedded newlines so records are never cut in half across files (with an optional `--raw-lines` mode for strict line-by-line splitting).
- **Flexible Chunk Sizing**: Split by a fixed maximum row count (default: `7000` data rows per file) or distribute rows evenly across files with `--equal`.
- **Zero Dependencies**: Uses only the Python standard library.

---

## Requirements

- Python 3.10 or newer

---

## Quick Start

Make the script executable (if not already):

```bash
chmod +x split_csv.py
```

Split a CSV file using the default of **7,000 data rows** per file:

```bash
./split_csv.py data.csv
```

Or run via `python3`:

```bash
python3 split_csv.py data.csv
```

For an input file named `data.csv` with 40,000 data rows (+ 1 header row), this generates:
- `data_part_001.csv` (1 header + 7,000 data rows = 7,001 lines)
- `data_part_002.csv` (1 header + 7,000 data rows = 7,001 lines)
- `data_part_003.csv` (1 header + 7,000 data rows = 7,001 lines)
- `data_part_004.csv` (1 header + 7,000 data rows = 7,001 lines)
- `data_part_005.csv` (1 header + 7,000 data rows = 7,001 lines)
- `data_part_006.csv` (1 header + 5,000 data rows = 5,001 lines)

---

## Command-Line Options

| Option | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `input` | — | *(Required)* | Path to the source CSV file. |
| `--rows <N>` | `-n` | `7000` | Maximum number of data rows (excluding header) per output file. |
| `--output-dir <DIR>` | `-o` | Input file's directory | Directory where split CSV files will be saved (created automatically if it does not exist). |
| `--prefix <STR>` | `-p` | `<input_stem>_part_` | Filename prefix for generated files (e.g., `custom_001.csv`). |
| `--equal` | `-e` | `False` | Distribute rows evenly across the minimum number of files so no file exceeds `--rows`. |
| `--raw-lines` | — | `False` | Split strictly by physical newline characters instead of parsing quoted CSV records. |
| `--help` | `-h` | — | Show help message and exit. |

---

## Usage Examples

### 1. Specify a custom row limit and output directory
Split `customers.csv` into chunks of 5,000 data rows and write them to `./output/`:
```bash
./split_csv.py customers.csv -n 5000 -o ./output
```

### 2. Balance rows evenly across output files (`--equal`)
If you have 40,000 data rows and want chunks of at most 7,000 rows, but prefer all files to have roughly the same size instead of a smaller final file:
```bash
./split_csv.py data.csv -n 7000 --equal
```
This calculates that 6 files are needed and places **6,667 data rows** (+ 1 header) in the first 4 files and **6,666 data rows** (+ 1 header) in the last 2 files.

### 3. Custom filename prefix
Generate files named `export_batch_001.csv`, `export_batch_002.csv`, etc.:
```bash
./split_csv.py data.csv -p export_batch_
```

### 4. Strict physical line splitting (`--raw-lines`)
If your file is guaranteed not to have multiline quoted values (or has malformed quotes you want to ignore) and you want to split strictly on physical lines:
```bash
./split_csv.py data.csv -n 7000 --raw-lines
```

---

## Using as a Python Module

You can also import and call `split_csv` directly from Python code:

```python
from pathlib import Path
from split_csv import split_csv

created_files = split_csv(
    input_path=Path("data.csv"),
    rows_per_file=7000,
    output_dir=Path("output_parts"),
    prefix="chunk_",
    equal_chunks=False,
    raw_lines=False,
)

for path in created_files:
    print(f"Created: {path}")
```

---

## How It Works

1. **Streaming & Memory Efficiency**: The splitter streams one record at a time and only holds the header and current row in memory, making it fast and suitable for very large CSV files.
2. **Raw Record Tracking (`_RawRowTracker`)**: Standard CSV readers parse and re-serialize rows, which can inadvertently alter delimiters, strip or add quotes, or change line endings. `split_csv.py` wraps the file stream in `_RawRowTracker`, allowing Python's `csv.reader` to detect record boundaries (including multiline quoted fields) while writing the exact original characters from the source file.
3. **Encoding Safety**: Files are opened with `encoding="utf-8", errors="surrogateescape"` and `newline=""`, allowing both UTF-8 (with or without BOM) and legacy 8-bit encodings (such as Windows-1250, ISO-8859-1/2) to pass through untouched without decoding errors.

