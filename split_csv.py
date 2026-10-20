#!/usr/bin/env python3
"""Split a CSV file into smaller CSV files while preserving the header row.

This module provides both a command-line interface and a programmatic API
(`split_csv`) for splitting large CSV files into smaller chunks. Every output
file receives an exact copy of the first (header) record from the source file.

Key characteristics:
- Preserves original formatting byte-for-byte (delimiters, quotes, line endings,
  UTF-8 BOM, and non-UTF-8 encodings via `surrogateescape`).
- Respects multiline quoted CSV fields by default so records are never split
  mid-field across files.
- Supports fixed-size chunks (default: 7,000 data rows) or evenly balanced
  chunks (`--equal`).
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys
from typing import Iterator, TextIO


class _RawRowTracker:
    """File iterator wrapper that captures the exact raw text consumed per CSV record.

    When passed to `csv.reader`, the reader advances through `_RawRowTracker`
    line by line until a complete logical CSV row (including any embedded
    newlines inside quoted fields) has been parsed. Calling `take_raw()` then
    returns the exact, unparsed string that formed that row.
    """

    def __init__(self, file_obj: TextIO) -> None:
        self._file_obj = file_obj
        self._buffer: list[str] = []

    def __iter__(self) -> _RawRowTracker:
        return self

    def __next__(self) -> str:
        line = next(self._file_obj)
        self._buffer.append(line)
        return line

    def take_raw(self) -> str:
        """Return and clear the buffered raw lines for the current CSV record."""
        raw = "".join(self._buffer)
        self._buffer.clear()
        return raw


def iter_records(file_obj: TextIO, raw_lines: bool = False) -> Iterator[str]:
    """Yield exact raw CSV records (or physical lines if `raw_lines=True`).

    Args:
        file_obj: Open text stream (opened with `newline=""`).
        raw_lines: If True, yield physical lines without CSV quote parsing.

    Yields:
        Exact raw string for each record/line, including its trailing newline.
    """
    if raw_lines:
        yield from file_obj
        return

    # Raise field size limit to handle large CSV cells without failing.
    csv.field_size_limit(sys.maxsize)
    tracker = _RawRowTracker(file_obj)
    reader = csv.reader(tracker)
    for _ in reader:
        yield tracker.take_raw()


def count_data_rows(input_path: Path, raw_lines: bool = False) -> int:
    """Count total data rows (excluding the first header row) in a CSV file.

    Args:
        input_path: Path to the source CSV file.
        raw_lines: If True, count physical lines rather than logical CSV records.

    Returns:
        Number of data rows after the header (0 if the file is empty or header-only).
    """
    with input_path.open("r", encoding="utf-8", errors="surrogateescape", newline="") as f:
        records = iter_records(f, raw_lines=raw_lines)
        try:
            next(records)  # Skip header
        except StopIteration:
            return 0
        return sum(1 for _ in records)


def split_csv(
    input_path: Path,
    rows_per_file: int = 7000,
    output_dir: Path | None = None,
    prefix: str | None = None,
    equal_chunks: bool = False,
    raw_lines: bool = False,
) -> list[Path]:
    """Split a CSV file into smaller files, repeating the first (header) row in each.

    Args:
        input_path: Path to the source CSV file.
        rows_per_file: Maximum number of data rows per output file (excluding header).
            Defaults to 7000.
        output_dir: Directory where split files will be written. Defaults to the
            same directory as `input_path`.
        prefix: Filename prefix for generated files. Defaults to `<input_stem>_part_`.
        equal_chunks: If True, pre-counts the rows and distributes them evenly across
            the minimum number of files needed so no file exceeds `rows_per_file`.
        raw_lines: If True, splits strictly on physical lines instead of parsing
            quoted multiline CSV fields.

    Returns:
        List of paths to the created output CSV files.

    Raises:
        ValueError: If `rows_per_file` is less than 1.
        FileNotFoundError: If `input_path` does not exist.
    """
    if rows_per_file <= 0:
        raise ValueError("rows_per_file must be a positive integer.")

    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    target_dir = output_dir if output_dir is not None else input_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    file_prefix = prefix if prefix is not None else f"{input_path.stem}_part_"
    suffix = input_path.suffix or ".csv"

    total_data_rows: int | None = None
    if equal_chunks:
        total_data_rows = count_data_rows(input_path, raw_lines=raw_lines)
        if total_data_rows > 0:
            num_files = math.ceil(total_data_rows / rows_per_file)
            rows_per_file = math.ceil(total_data_rows / num_files)

    created_files: list[Path] = []

    with input_path.open("r", encoding="utf-8", errors="surrogateescape", newline="") as infile:
        records = iter_records(infile, raw_lines=raw_lines)
        try:
            header = next(records)
        except StopIteration:
            return created_files

        # Ensure header ends with a newline in case the file only had 1 line without newline
        if not header.endswith(("\n", "\r")):
            header += "\n"

        part_num = 0
        current_row_count = 0
        outfile: TextIO | None = None

        try:
            for record in records:
                if outfile is None or current_row_count >= rows_per_file:
                    if outfile is not None:
                        outfile.close()
                    part_num += 1
                    out_path = target_dir / f"{file_prefix}{part_num:03d}{suffix}"
                    outfile = out_path.open(
                        "w", encoding="utf-8", errors="surrogateescape", newline=""
                    )
                    outfile.write(header)
                    created_files.append(out_path)
                    current_row_count = 0

                outfile.write(record)
                current_row_count += 1
        finally:
            if outfile is not None:
                outfile.close()

    return created_files


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Split a CSV file into smaller chunks while preserving the header row.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ./split_csv.py data.csv\n"
            "  ./split_csv.py data.csv -n 7000 -o ./chunks\n"
            "  ./split_csv.py data.csv -n 7000 --equal\n"
            "  ./split_csv.py data.csv -p custom_prefix_ --raw-lines\n"
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the source CSV file.",
    )
    parser.add_argument(
        "-n",
        "--rows",
        type=int,
        default=7000,
        help="Number of data rows per split file (default: 7000).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for split files (default: same directory as input file).",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        type=str,
        default=None,
        help="Filename prefix for generated parts (default: '<input_stem>_part_').",
    )
    parser.add_argument(
        "-e",
        "--equal",
        action="store_true",
        help="Balance row counts evenly across parts (keeping each part <= --rows).",
    )
    parser.add_argument(
        "--raw-lines",
        action="store_true",
        help="Split strictly by physical lines instead of parsing quoted CSV records.",
    )

    args = parser.parse_args()

    try:
        output_files = split_csv(
            input_path=args.input,
            rows_per_file=args.rows,
            output_dir=args.output_dir,
            prefix=args.prefix,
            equal_chunks=args.equal,
            raw_lines=args.raw_lines,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not output_files:
        print("No data rows found to split.")
        return 0

    print(f"Created {len(output_files)} file(s):")
    for path in output_files:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
