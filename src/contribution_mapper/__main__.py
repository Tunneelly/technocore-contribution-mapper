"""Command-line entry point for Technocore Contribution Mapper."""

import argparse
import sys

from contribution_mapper.runner import run_mapper


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare public GitHub repository metadata with references "
            "in a public Technocore room. Text matches are not proof."
        )
    )
    parser.add_argument("owner", help="GitHub repository owner")
    parser.add_argument("repository", help="GitHub repository name")
    parser.add_argument("--room", default="lobby", help="Technocore room")
    parser.add_argument("--artifact-url", help="Exact artifact URL to search for")
    parser.add_argument("--commit", help="Full 40-character Git commit SHA")
    parser.add_argument(
        "--output",
        default="contribution-report.json",
        help="Local JSON output path",
    )
    parser.add_argument(
        "--source",
        choices=("recent", "export"),
        default="recent",
        help=(
            "recent: latest batch only; export: the room's full retained "
            "window (still not complete history)"
        ),
    )
    parser.add_argument(
        "--proof",
        help="Signed contribution proof JSON to verify (public file only)",
    )
    args = parser.parse_args()

    try:
        report = run_mapper(
            args.owner,
            args.repository,
            args.room,
            artifact_url=args.artifact_url,
            commit=args.commit,
            output=args.output,
            source=args.source,
            proof_file=args.proof,
        )
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Mapper error: {error}", file=sys.stderr)
        return 1

    print(f"Report saved to: {args.output}")
    print(f"Repository: {report['repository']['full_name']}")
    print(f"Evidence records: {report['evidence']['record_count']}")
    print(
        "Authorship verified by text matching: "
        f"{report['interpretation']['text_matches_prove_authorship']}"
    )
    coverage = report["retrieval_coverage"]
    print(
        f"Examined {coverage['messages_examined']} messages "
        f"(seq {coverage['first_seq_examined']} to "
        f"{coverage['last_seq_examined']}); "
        "complete history searched: "
        f"{coverage['complete_history_searched']}"
    )
    proof = report["proof_verification"]
    print(f"Signed proof: {proof['status']}")
    if proof["status"] == "valid":
        print(f"  signed by {proof['did']}")
        print(f"  commit {proof['commit']}")
        print(
            "  matches --artifact-url: "
            f"{proof['artifact_url_matches_request']}; "
            f"matches --commit: {proof['commit_matches_request']}"
        )
        print("  This does not prove authorship of the commit.")
    elif proof.get("reason"):
        print(f"  {proof['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
