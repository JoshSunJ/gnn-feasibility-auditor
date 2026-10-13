"""Command-line audit and independent certificate verification."""

import argparse
import json
from pathlib import Path
import sys

from .data import InputError, load_dataset
from .report import audit, text_report
from .verify import VerificationError, verify_report


def _nonnegative(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return n


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Exact feature-aware 1-WL training feasibility auditor")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("audit", help="compute training ceiling and cross-label witnesses")
    run.add_argument("dataset", type=Path)
    run.add_argument("--format", choices=["text", "json"], default="text")
    run.add_argument("--engine", choices=["trace", "partition"], default="trace", help="full synchronous trace or compact exact partition certificate")
    run.add_argument("--max-pairs", type=_nonnegative, default=20)
    run.add_argument("--certificate", action="store_true", help="include replayable proof trace (JSON only)")
    run.add_argument("--output", type=Path, help="save report; otherwise print to stdout")
    check = commands.add_parser("verify", help="independently replay a JSON certificate against actual inputs")
    check.add_argument("dataset", type=Path)
    check.add_argument("report", type=Path)
    bench = commands.add_parser("benchmark", help="optional CPU GIN/GCN training fits, after certificate verification")
    bench.add_argument("dataset", type=Path)
    bench.add_argument("--models", nargs="+", choices=["gin", "gcn"], default=["gin", "gcn"])
    bench.add_argument("--seeds", nargs="+", type=_nonnegative, default=[0, 1, 2])
    bench.add_argument("--epochs", type=int, default=300)
    bench.add_argument("--hidden", type=int, default=32)
    bench.add_argument("--layers", type=int, default=3)
    bench.add_argument("--learning-rate", type=float, default=.01)
    bench.add_argument("--output", type=Path)
    explore = commands.add_parser("explore", help="export a self-contained visual interface from a verified audit")
    explore.add_argument("dataset", type=Path)
    explore.add_argument("--output", type=Path, required=True)
    explore.add_argument("--benchmark", type=Path, help="attach measured benchmark JSON")
    explore.add_argument("--engine", choices=["trace", "partition"], default="trace")
    return root


def main(argv: list[str] | None = None) -> int:
    root = parser()
    args = root.parse_args(argv)
    try:
        dataset = load_dataset(args.dataset)
        if args.command == "verify":
            report = json.loads(args.report.read_text(encoding="utf-8"))
            verify_report(dataset, report)
            print("Verified: exact 1-WL evidence, stability, equivalence classes, witnesses and training ceiling.")
            return 0
        if args.command == "benchmark":
            from .benchmark import BenchmarkError, run_benchmarks
            try:
                result = run_benchmarks(dataset, models=args.models, seeds=args.seeds, epochs=args.epochs,
                                        hidden=args.hidden, layers=args.layers, learning_rate=args.learning_rate)
            except BenchmarkError as error:
                print(f"gnn-audit: {error}", file=sys.stderr)
                return 2
            output = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
            if args.output:
                args.output.write_text(output, encoding="utf-8")
            else:
                sys.stdout.write(output)
            return 0
        if args.command == "explore":
            from .explorer import render_html, render_verified_html
            measured = json.loads(args.benchmark.read_text(encoding="utf-8")) if args.benchmark else None
            try:
                if args.engine == "partition":
                    from .partition import audit_partition
                    output = render_verified_html(dataset, audit_partition(dataset, max_pairs=100, include_certificate=True), measured)
                else:
                    output = render_html(dataset, measured)
            except ValueError as error:
                print(f"gnn-audit: {error}", file=sys.stderr)
                return 2
            args.output.write_text(output, encoding="utf-8")
            print(f"Saved verified graph explorer: {args.output}")
            return 0
        if args.certificate and args.format != "json":
            root.error("--certificate requires --format json")
        if args.engine == "partition":
            from .partition import audit_partition
            report = audit_partition(dataset, args.max_pairs, args.certificate)
        else:
            report = audit(dataset, args.max_pairs, args.certificate)
        output = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n" if args.format == "json" else text_report(report)
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0
    except (InputError, VerificationError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"gnn-audit: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
