#!/usr/bin/env python3
"""Sync SBI forex card rates PDFs and compact JSON data."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from dateutil import parser as date_parser
from pypdf import PdfReader

SBI_DAILY_RATES_URL = "https://sbi.bank.in/documents/16012/1400784/FOREX_CARD_RATES.pdf"
SBI_DAILY_RATES_URL_FALLBACK = "https://bank.sbi/documents/16012/1400784/FOREX_CARD_RATES.pdf"
JSON_HEADER = ["date", "tt_buy", "tt_sell"]
TARGET_CURRENCY = "USD"

CURRENCY_LINE_REGEX = re.compile(r"([A-Z]{3})/INR\s*((?:\d+(?:\.\d+)?\s?)+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync SBI FX card rates data")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Target repository root that contains src/ and docs/ folders",
    )
    parser.add_argument(
        "--source-repo",
        default=None,
        help="Path to sbi-fx-ratekeeper for historical migration",
    )
    parser.add_argument(
        "--migrate-historical",
        action="store_true",
        help="Migrate historical PDFs and rates from source repo",
    )
    parser.add_argument(
        "--fetch-latest",
        action="store_true",
        help="Download the latest PDF from SBI and update JSON files",
    )
    return parser.parse_args()


def ensure_dirs(repo_root: Path) -> Tuple[Path, Path]:
    src_root = repo_root / "src" / "sbi-fx-card-rates"
    data_root = repo_root / "docs" / "sbi-fx-card-rates"
    src_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    return src_root, data_root


def parse_date_from_datetime_string(value: str) -> str:
    # CSV stores datetime as YYYY-MM-DD HH:MM
    if not value:
        raise ValueError("DATE column is empty")
    return value.strip().split()[0]


def write_compact_json(file_path: Path, rows_by_date: Dict[str, Tuple[float, float]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_dates = sorted(rows_by_date.keys())
    payload = {
        "header": JSON_HEADER,
        "data": [[d, rows_by_date[d][0], rows_by_date[d][1]] for d in sorted_dates],
    }
    file_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def migrate_historical(source_repo: Path, repo_root: Path) -> None:
    src_root, data_root = ensure_dirs(repo_root)

    source_pdf_root = source_repo / "pdf_files"
    if not source_pdf_root.exists():
        raise FileNotFoundError(f"Missing source pdf folder: {source_pdf_root}")

    for pdf_path in source_pdf_root.glob("*/*/*.pdf"):
        year = pdf_path.parts[-3]
        target_dir = src_root / year
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / pdf_path.name
        if not target_path.exists():
            shutil.copy2(pdf_path, target_path)

    source_csv_root = source_repo / "csv_files"
    if not source_csv_root.exists():
        raise FileNotFoundError(f"Missing source csv folder: {source_csv_root}")

    csv_path = source_csv_root / f"SBI_REFERENCE_RATES_{TARGET_CURRENCY}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing source csv file: {csv_path}")

    by_year: Dict[str, Dict[str, Tuple[float, float]]] = defaultdict(dict)
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_date = parse_date_from_datetime_string(row.get("DATE", ""))
            year = row_date[:4]
            tt_buy_raw = (row.get("TT BUY") or "").strip() or "0"
            tt_sell_raw = (row.get("TT SELL") or "").strip() or "0"
            tt_buy = float(tt_buy_raw)
            tt_sell = float(tt_sell_raw)
            by_year[year][row_date] = (tt_buy, tt_sell)

    for year, rows in by_year.items():
        out_path = data_root / year / f"{TARGET_CURRENCY}.json"
        write_compact_json(out_path, rows)


def extract_date_time(text: str) -> datetime:
    date_line = next(
        (line for line in text.split("\n") if line.strip().lower().startswith("date")),
        None,
    )
    time_line = next(
        (line for line in text.split("\n") if line.strip().lower().startswith("time")),
        None,
    )
    if not date_line or not time_line:
        raise ValueError("Unable to find date/time lines in PDF text")

    parsed_date = date_parser.parse(date_line, fuzzy=True, dayfirst=True).date()
    parsed_time = date_parser.parse(time_line, fuzzy=True).time()
    return datetime.combine(parsed_date, parsed_time)


def extract_tt_rates(reference_text: str) -> Dict[str, Tuple[float, float]]:
    rows: Dict[str, Tuple[float, float]] = {}
    for line in reference_text.split("\n"):
        match = CURRENCY_LINE_REGEX.search(line)
        if not match:
            continue
        currency, rates_blob = match.groups()
        rates = rates_blob.strip().split()
        if len(rates) < 2:
            continue
        rows[currency] = (float(rates[0]), float(rates[1]))

    if not rows:
        raise ValueError("Unable to parse TT rates from PDF")
    return rows


def parse_pdf_rates(pdf_bytes: bytes) -> Tuple[date, Dict[str, Tuple[float, float]]]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if not reader.pages:
        raise ValueError("PDF does not contain pages")

    first_page_text = reader.pages[0].extract_text() or ""
    published_dt = extract_date_time(first_page_text)

    reference_page_text = ""
    for page in reader.pages[:2]:
        page_text = page.extract_text() or ""
        if "to be used as reference rates" in page_text.lower():
            reference_page_text = page_text
            break

    if not reference_page_text:
        raise ValueError("Reference rates block not found in first two pages")

    return published_dt.date(), extract_tt_rates(reference_page_text)


def load_rows(path: Path) -> Dict[str, Tuple[float, float]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    data = payload.get("data", [])
    rows: Dict[str, Tuple[float, float]] = {}
    for row in data:
        if len(row) < 3:
            continue
        rows[str(row[0])] = (float(row[1]), float(row[2]))
    return rows


def download_latest_pdf() -> bytes:
    urls = [SBI_DAILY_RATES_URL, SBI_DAILY_RATES_URL_FALLBACK]
    last_error: Optional[Exception] = None

    for url in urls:
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            if response.content.startswith(b"%PDF"):
                return response.content
            raise ValueError("Response is not a PDF")
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    raise RuntimeError(f"Failed to download latest PDF: {last_error}")


def update_with_latest(repo_root: Path) -> None:
    src_root, data_root = ensure_dirs(repo_root)
    pdf_bytes = download_latest_pdf()
    published_date, rates = parse_pdf_rates(pdf_bytes)

    year = str(published_date.year)
    date_str = published_date.strftime("%Y-%m-%d")

    year_src = src_root / year
    year_src.mkdir(parents=True, exist_ok=True)
    (year_src / f"{date_str}.pdf").write_bytes(pdf_bytes)

    if TARGET_CURRENCY not in rates:
        raise ValueError(f"{TARGET_CURRENCY} not found in latest PDF rates")

    tt_buy, tt_sell = rates[TARGET_CURRENCY]
    json_path = data_root / year / f"{TARGET_CURRENCY}.json"
    rows = load_rows(json_path)
    rows[date_str] = (tt_buy, tt_sell)
    write_compact_json(json_path, rows)


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    if not args.migrate_historical and not args.fetch_latest:
        print("Nothing to do. Use --migrate-historical and/or --fetch-latest.")
        return 1

    if args.migrate_historical:
        if not args.source_repo:
            raise ValueError("--source-repo is required with --migrate-historical")
        source_repo = Path(args.source_repo).resolve()
        migrate_historical(source_repo, repo_root)
        print("Historical migration complete")

    if args.fetch_latest:
        update_with_latest(repo_root)
        print("Latest rates update complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
