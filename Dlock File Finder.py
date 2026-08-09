#!/usr/bin/env python3
"""
Duplicate File Finder

A clean, open-source command-line utility that scans a directory (or an
entire drive) and finds identical duplicate files — even if their names
are completely different. It compares files by their digital fingerprint
(MD5 hash), not by name, and can safely remove the extra copies.

Usage:
    python duplicate_finder.py <path> [--delete] [--dry-run] [--yes]

    Or just double-click the file for interactive mode.
"""

import argparse
import hashlib
import os
import sys
import time
from collections import defaultdict

# ─── Configuration ───────────────────────────────────────────────────────────
CHUNK_SIZE = 65536  # 64 KB read block size for hashing

# ─── ANSI Colors ─────────────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"


# Enable ANSI colors and UTF-8 on Windows
if sys.platform == "win32":
    os.system("")
    os.system("chcp 65001 > nul 2>&1")

# Ensure UTF-8 output for Unicode characters
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_file_size(path):
    """Return file size in bytes, or None if inaccessible."""
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def compute_hash(path):
    """Compute and return MD5 hex digest of a file, or None on error."""
    hasher = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def format_size(num_bytes):
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def print_header(title, icon=""):
    """Print a styled section header with rounded corners."""
    width = 56
    label = f"{icon}  {title}" if icon else title
    print()
    print(f"{C.CYAN}╭{'─' * width}╮{C.RESET}")
    padded = label.center(width)
    print(f"{C.CYAN}│{C.BOLD}{padded}{C.RESET}{C.CYAN}│{C.RESET}")
    print(f"{C.CYAN}╰{'─' * width}╯{C.RESET}")


def print_banner():
    """Print the application banner."""
    top    = f"{C.CYAN}╭{'─' * 44}╮{C.RESET}"
    bottom = f"{C.CYAN}╰{'─' * 44}╯{C.RESET}"
    side   = f"{C.CYAN}│{C.RESET}"

    b = chr(92)  # backslash
    lines = [
        f"  ____  _            _",
        f" |  _ {b}| | ___   ___| | __",
        f" | | | | |/ _ {b} / __| |/ /",
        f" | |_| | | (_) | (__|   <",
        f" |____/|_|{b}___/ {b}___|_|{b}_{b}",
    ]

    print()
    print(f"  {top}")
    for line in lines:
        print(f"  {side}         {C.GREEN}{C.BOLD}{line}{C.RESET}         {side}")
    print(f"  {side}{'':44}{side}")
    print(f"  {side}              {C.CYAN}{C.BOLD}Finder v1.0{C.RESET}              {side}")
    print(f"  {side}{'':44}{side}")
    print(f"  {side}  {C.DIM}Find & remove duplicate files by hash{C.RESET}  {side}")
    print(f"  {side}  {C.DIM}Open-source | Python | No deps{C.RESET}          {side}")
    print(f"  {bottom}")
    print()


def print_progress(current, total, bar_width=32):
    """Print a progress bar to the terminal."""
    if total == 0:
        return
    fraction = current / total
    filled = int(bar_width * fraction)
    bar = "█" * filled + "░" * (bar_width - filled)
    percent = int(fraction * 100)
    sys.stdout.write(f"\r  {C.CYAN}⏳ [{bar}] {percent}% ({current}/{total}){C.RESET}")
    sys.stdout.flush()
    if current >= total:
        print(f"\r  {C.GREEN}✅ [{bar}] 100% ({current}/{total}){C.RESET}  ")
        print()


# ─── Core Logic ──────────────────────────────────────────────────────────────

def scan_directory(root):
    """Walk a directory tree and return a list of all file paths."""
    all_files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if os.path.isfile(full):
                all_files.append(full)
    return all_files


def find_duplicates(files):
    """
    Find duplicates among a list of files.

    Two-stage algorithm:
      1. Group by file size (fast filter).
      2. Hash only files that share a size with at least one other file.
      3. Files with matching (size, hash) are duplicates.

    Returns a list of groups, where each group is a list of file paths
    with identical content.
    """
    # --- Stage 1: group by size ---
    by_size = defaultdict(list)
    for path in files:
        size = get_file_size(path)
        if size is not None:
            by_size[size].append(path)

    # Keep only sizes shared by more than one file
    candidates = [paths for paths in by_size.values() if len(paths) > 1]

    # --- Stage 2: group by hash ---
    by_hash = defaultdict(list)
    files_to_hash = sum(len(g) for g in candidates)
    hashed = 0

    for group in candidates:
        for path in group:
            digest = compute_hash(path)
            hashed += 1
            print_progress(hashed, files_to_hash)
            if digest is not None:
                key = (get_file_size(path), digest)
                by_hash[key].append(path)

    # Groups with more than one file are duplicates
    duplicates = [paths for paths in by_hash.values() if len(paths) > 1]
    return duplicates


# ─── Output ──────────────────────────────────────────────────────────────────

def print_results(duplicates):
    """Print found duplicates in a formatted, color-coded layout."""
    if not duplicates:
        print(f"\n  {C.GREEN}✅ No duplicates found! Your folders are clean.{C.RESET}\n")
        return 0

    total_waste = 0
    total_files = sum(len(g) for g in duplicates)

    print_header(f"FOUND {len(duplicates)} DUPLICATE GROUPS", "🔍")

    for i, group in enumerate(duplicates, 1):
        size = get_file_size(group[0])
        waste = size * (len(group) - 1)
        total_waste += waste

        print()
        print(f"  {C.YELLOW}{C.BOLD}┌─ Group {i}{C.RESET}  "
              f"{C.DIM}│{C.RESET}  "
              f"{C.WHITE}📄 {len(group)} files{C.RESET}  "
              f"{C.DIM}│{C.RESET}  "
              f"{C.WHITE}{format_size(size)} each{C.RESET}")

        for j, path in enumerate(group, 1):
            if j == 1:
                icon = f"{C.GREEN}  ✅ KEEP{C.RESET}"
                label = f"{C.GREEN}{path}{C.RESET}  {C.DIM}(original){C.RESET}"
            else:
                icon = f"{C.RED}  ❌ DUPE{C.RESET}"
                label = f"{C.DIM}{path}{C.RESET}"
            print(f"  {C.YELLOW}│{C.RESET}{icon}  {label}")

        print(f"  {C.YELLOW}└─{C.RESET}  {C.MAGENTA}💾 Wasted: {format_size(waste)}{C.RESET}")

    print()
    print(f"  {C.CYAN}╭{'─' * 52}╮{C.RESET}")
    print(f"  {C.CYAN}│{C.RESET}  {C.BOLD}📊 Summary{C.RESET}                                    {C.CYAN}│{C.RESET}")
    print(f"  {C.CYAN}├{'─' * 52}┤{C.RESET}")
    print(f"  {C.CYAN}│{C.RESET}  🔸 Duplicate groups  : {C.YELLOW}{len(duplicates)}{C.RESET}                    {C.CYAN}│{C.RESET}")
    print(f"  {C.CYAN}│{C.RESET}  🔸 Total dupes       : {C.YELLOW}{total_files - len(duplicates)}{C.RESET}                    {C.CYAN}│{C.RESET}")
    print(f"  {C.CYAN}│{C.RESET}  🔸 Reclaimable space : {C.GREEN}{C.BOLD}{format_size(total_waste)}{C.RESET}                    {C.CYAN}│{C.RESET}")
    print(f"  {C.CYAN}╰{'─' * 52}╯{C.RESET}")
    print()
    return total_waste


def delete_duplicates(duplicates, dry_run=False):
    """
    Delete duplicates, keeping one original per group.
    The first file in each group is treated as the original and is kept.

    In dry_run mode, only shows what would be deleted.
    """
    deleted_count = 0
    freed_bytes = 0

    print_header("DELETING DUPLICATES" if not dry_run
                 else "DRY RUN — NO FILES WILL BE TOUCHED", "🗑️" if not dry_run else "👀")

    for group in duplicates:
        for path in group[1:]:
            size = get_file_size(path)
            if dry_run:
                print(f"  {C.YELLOW}  👀 [DRY-RUN]{C.RESET} Would delete: {path}")
            else:
                try:
                    os.remove(path)
                    print(f"  {C.RED}  🗑️ [DELETED]{C.RESET} {path}")
                except OSError as e:
                    print(f"  {C.RED}  ⚠️ [ERROR]{C.RESET} Could not delete {path}: {e}")
                    continue
            deleted_count += 1
            if size is not None:
                freed_bytes += size

    print()
    label = "DRY RUN" if dry_run else "DONE"
    icon = "👀" if dry_run else "✅"
    print(f"  {C.BOLD}{icon} {label}:{C.RESET} "
          f"{C.YELLOW}{deleted_count}{C.RESET} file(s) processed, "
          f"{C.GREEN}{format_size(freed_bytes)}{C.RESET} would be freed.")
    print()


# ─── Interaction ─────────────────────────────────────────────────────────────

def confirm(prompt):
    """Ask user for y/n confirmation."""
    while True:
        answer = input(f"{C.BOLD}{prompt}{C.RESET} {C.DIM}[y/n]{C.RESET}: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


def run_scan(path, delete=False, dry_run=False, auto_yes=False):
    """Run the full scan and optionally delete duplicates."""
    print(f"\n  {C.CYAN}📁 Scanning:{C.RESET} {path}")
    print(f"  {C.DIM}📂 Collecting file list...{C.RESET}")

    files = scan_directory(path)
    print(f"  {C.WHITE}📊 Found {len(files)} files{C.RESET}")

    if not files:
        print(f"\n  {C.YELLOW}⚠️ No files found in this directory.{C.RESET}")
        return

    print(f"  {C.DIM}🔐 Hashing files with matching sizes...{C.RESET}")
    t0 = time.time()
    duplicates = find_duplicates(files)
    elapsed = time.time() - t0

    print(f"  {C.DIM}⏱️ Scan completed in {elapsed:.2f}s{C.RESET}")
    print_results(duplicates)

    if delete and duplicates:
        if dry_run:
            delete_duplicates(duplicates, dry_run=True)
        else:
            if auto_yes or confirm("Delete duplicates? Originals will be kept."):
                delete_duplicates(duplicates, dry_run=False)
            else:
                print(f"\n  {C.YELLOW}🚫 Deletion cancelled by user.{C.RESET}\n")


def interactive_mode():
    """Interactive mode for when the script is launched by double-click."""
    print_banner()

    path = input(f"  {C.BOLD}📁 Enter folder path to scan:{C.RESET} ").strip().strip('"')
    if not path:
        print(f"\n  {C.RED}❌ No path provided. Exiting.{C.RESET}")
        input(f"\n  {C.DIM}Press Enter to exit...{C.RESET}")
        return

    if not os.path.isdir(path):
        print(f"\n  {C.RED}❌ Error: '{path}' is not a valid directory.{C.RESET}")
        input(f"\n  {C.DIM}Press Enter to exit...{C.RESET}")
        return

    print()
    print(f"  {C.BOLD}⚙️ Select mode:{C.RESET}")
    print(f"    {C.GREEN}1{C.RESET} — 🔍 Scan only (find duplicates, no deletion)")
    print(f"    {C.RED}2{C.RESET} — 🗑️ Scan & delete (keep originals, remove dupes)")
    choice = input(f"  {C.BOLD}Choice [1/2]{C.RESET} {C.DIM}(default: 1){C.RESET}: ").strip() or "1"

    delete = choice == "2"

    run_scan(path, delete=delete, dry_run=False, auto_yes=False)

    input(f"\n  {C.DIM}Press Enter to exit...{C.RESET}")


def main():
    # If arguments are provided — run in CLI mode
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description="Find and remove duplicate files by content hash.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            "path",
            help="Directory path to scan",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete duplicates (with confirmation). Without this flag, "
                 "only a scan is performed.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting anything.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt and delete automatically.",
        )
        args = parser.parse_args()

        if not os.path.isdir(args.path):
            print(f"{C.RED}Error: '{args.path}' is not a valid directory.{C.RESET}")
            sys.exit(1)

        run_scan(args.path, delete=args.delete, dry_run=args.dry_run,
                 auto_yes=args.yes)
    else:
        # No arguments — launch interactive mode (double-click)
        interactive_mode()


if __name__ == "__main__":
    main()
