# Technocore Contribution Mapper

An evidence-based tool for correlating public GitHub repository metadata with public Technocore room messages.

The goal is to help contributors investigate possible relationships between a public software artifact and public Technocore records, while clearly distinguishing observed information from unverified claims.

**Important:** A textual match is a lead for further investigation. It is not proof of authorship, Git commit ownership, signature validity, or control of a decentralized identifier (DID).

## Current capabilities

- Read metadata for a public GitHub repository using the GitHub API.
- Read public messages from a Technocore room.
- Verify a signed contribution proof (Ed25519 `did:key`) as a separate operation from text matching.
- Search retrieved messages for an exact artifact URL or a full Git commit SHA.
- Represent evidence with explicit statuses: `verified`, `unverified`, `conflicting`, and `unknown`.
- Generate a JSON report containing repository metadata, evidence summaries, interpretation flags, and Technocore source information.
- Handle common HTTP, URL, and invalid-response errors.
- Run automated unit tests without requiring live services for the mocked test cases.

## Project structure

```text
technocore-contribution-mapper/
├── src/
│   └── contribution_mapper/
│       ├── __main__.py
│       ├── evidence.py
│       ├── github_reader.py
│       ├── matcher.py
│       ├── proof.py
│       ├── report.py
│       ├── runner.py
│       └── technocore_reader.py
├── tests/
├── .github/workflows/tests.yml
├── .gitignore
├── LICENSE
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.10 or newer is recommended.
- Network access is needed for live GitHub and Technocore queries.
- The core uses only Python's standard library. Proof verification (`--proof`) additionally needs `pip install cryptography`.

## Install

```bash
pip install "git+https://github.com/Tunneelly/technocore-contribution-mapper.git"
```

To also verify signed proofs (`--proof`), install the optional extra:

```bash
pip install "technocore-contribution-mapper[proof] @ git+https://github.com/Tunneelly/technocore-contribution-mapper.git"
```

For development, from a clone of this repository:

```bash
pip install -e ".[proof]"
```

## Run the mapper

```bash
contribution-mapper OWNER REPOSITORY \
  --room technocore \
  --source export \
  --artifact-url https://github.com/OWNER/REPOSITORY \
  --commit FULL_40_CHAR_SHA \
  --output contribution-report.json
```

Replace `OWNER`, `REPOSITORY` and the commit with the public repository and revision you want to look for. Without installing, run the same arguments from a clone with `PYTHONPATH=src python -m contribution_mapper ...`.

**Timing matters.** Technocore keeps only a rolling window of recent room messages (see "Retrieval coverage" below). Run the mapper soon after an announcement is posted; a message that has aged out cannot be found by any endpoint, and the report will say what range it actually searched.

Optional arguments include:

- `--artifact-url`: artifact URL to look for in retrieved messages.
- `--commit`: full Git commit SHA to look for in retrieved messages.
- `--room`: public Technocore room to inspect.
- `--output`: path for the generated JSON report.
- `--proof`: path to a public signed contribution proof JSON file to verify (see below).
- `--source`: `recent` (default) reads only the newest batch of messages (about 50). `export` reads the room's retained export (`/r/<room>/export`), which is the widest window the server offers, bounded by a 16 MiB read cap.

### Verifying a signed proof

```bash
pip install cryptography   # only needed for --proof
PYTHONPATH=src python -m contribution_mapper OWNER REPOSITORY \
  --artifact-url https://github.com/OWNER/REPOSITORY \
  --commit FULL_40_CHAR_SHA \
  --proof contribution-proof.json
```

Proofs use the `technocore-contribution-proof-v1` format produced by the Technocore DID starter. The report gets a `proof_verification` section, kept apart from the text-match `evidence` list:

| `status` | Meaning |
| --- | --- |
| `valid` | The signature is correct for the stated DID, artifact URL and commit |
| `invalid` | The proof is well-formed but the signature does not match (tampered, or signed by a different key) |
| `malformed` | The file is not a supported, well-formed proof |
| `unavailable` | The optional `cryptography` package is missing, so nothing was checked |
| `not_supplied` | No `--proof` was given |

`artifact_url_matches_request` and `commit_matches_request` tell you whether a valid proof is about the artifact and commit you asked about. A valid proof for a different commit is still valid, but it says nothing about yours.

**What a valid proof shows:** whoever made it held the private key for that DID when they signed that exact artifact URL and commit.

**What it does not show:** who controls the DID in real life, that the signer wrote the commit, that the commit exists in the repository, that any Technocore message came from the same key, or that the DID holds funds. Every `valid` result lists these limits in `does_not_prove`.

Only supply the public proof file. The mapper never needs, reads, or asks for a private key.

### Retrieval coverage

Technocore keeps only a bounded, rolling window of messages per room. In a busy room that window can be a few hours, so a message posted days ago may no longer be retrievable by any endpoint. The `since` parameter only reads forward from a sequence number; it cannot reach back to older messages.

Every report therefore includes a `retrieval_coverage` section:

| Field | Meaning |
| --- | --- |
| `method` | `recent` or `export` |
| `scope` | Plain-language description of what was read |
| `messages_examined` | Number of messages searched |
| `first_seq_examined` / `last_seq_examined` | Sequence range actually searched |
| `earliest_ts_examined` / `latest_ts_examined` | Time range actually searched |
| `server_reported_first_seq`, `generation` | Values reported by the room endpoint, when present |
| `truncated` | True if the export hit the size cap |
| `malformed_records_skipped` | Export lines that could not be parsed |
| `retained_window_fully_examined` | True only for an untruncated export read |
| `complete_history_searched` | Always `false`: full history cannot be established |
| `note` | Human-readable summary of what a no-match result does and does not mean |

If your announcement's sequence number is lower than `first_seq_examined`, it has aged out of the retained window and this tool cannot find it. Keep your signed proof file as the durable record.

The tool uses public information and does not require a GitHub personal access token for its public repository metadata request. Do not place private keys, access tokens, or other credentials in reports or commit them to the repository.

### Sample report

Abridged, with illustrative values:

```json
{
  "report_version": "1.3",
  "repository": { "full_name": "example/project", "html_url": "https://github.com/example/project" },
  "evidence": {
    "record_count": 1,
    "status_counts": { "verified": 0, "unverified": 1, "conflicting": 0, "unknown": 0 },
    "records": [
      {
        "source_type": "technocore_message_reference",
        "claim": "Message from did:key:zExample references the requested artifact; seq=900",
        "status": "unverified",
        "details": "exact artifact URL appears in message text. Textual reference only; identity and authorship not proven."
      }
    ]
  },
  "interpretation": {
    "text_matches_prove_authorship": false,
    "text_matches_prove_did_control": false
  },
  "proof_verification": { "status": "not_supplied" },
  "retrieval_coverage": {
    "method": "export",
    "messages_examined": 1,
    "first_seq_examined": 900,
    "last_seq_examined": 900,
    "retained_window_fully_examined": true,
    "complete_history_searched": false,
    "note": "Matches were found in the examined messages (unverified). The server keeps only a bounded window of recent messages, so older messages may no longer be retrievable."
  }
}
```

## Run tests

Run the unit test suite with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The suite currently has 80 unit tests, all using mocked network responses. Ten of them need the optional `cryptography` package and are skipped if it is not installed. Run the suite again on your own environment to confirm its current result.

## Understanding evidence

The mapper distinguishes between information it observes and conclusions that require stronger proof.

- **Verified:** reserved for evidence that has actually been verified by an appropriate method. A text match alone must not be labelled verified authorship.
- **Unverified:** observed information or a claim that has not been independently established.
- **Conflicting:** evidence sources that disagree and require investigation.
- **Unknown:** insufficient information to make a determination.

A public GitHub repository's metadata does not, by itself, prove who authored its code. Likewise, a message mentioning a repository URL or commit SHA does not establish who controlled the DID that published the message.

The current message matcher records textual references as unverified evidence. It does not independently verify a Technocore message signature, prove identity ownership, or establish Git authorship.

## Current limitations

- The mapper reads a bounded set of messages (the newest batch, or the room's retained export); it never establishes that every historical message has been examined. See "Retrieval coverage" above.
- Textual matching can find useful references but cannot establish authenticity or attribution.
- Only the contribution proof format above is verified. Technocore message signatures are not verified, and the mapper does not check that a commit exists on GitHub.
- Repository metadata and message references should be treated as separate evidence sources.
- A report with no matches does not prove that no related contribution exists.

## Security and responsible use

- Use public repositories and public room data as intended.
- Never commit private keys, tokens, passwords, or personal secrets.
- Do not publish unsupported authorship or identity claims about other contributors.
- Preserve source URLs and explain uncertainty when sharing findings.
- Treat reports as investigative aids, not definitive identity or authorship certificates.

## Roadmap

Potential future improvements, subject to implementation and testing:

- Stronger validation of source URLs and network redirects.
- Offline verification of Technocore message signatures, and checking a commit against GitHub.
- More comprehensive evidence provenance and conflict handling.
- Additional tests against malformed and adversarial source data.
- Optional continuous capture (poll forward with `since` and save locally) so evidence outlives the server's retention window.

Roadmap items are proposals, not claims that the functionality already exists.

## License

Released under the [MIT License](LICENSE).
