# Technocore Contribution Mapper

An evidence-based tool for correlating public GitHub repository metadata with public Technocore room messages.

The goal is to help contributors investigate possible relationships between a public software artifact and public Technocore records, while clearly distinguishing observed information from unverified claims.

**Important:** A textual match is a lead for further investigation. It is not proof of authorship, Git commit ownership, signature validity, or control of a decentralized identifier (DID).

## Current capabilities

- Read metadata for a public GitHub repository using the GitHub API.
- Read public messages from a Technocore room.
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
│       ├── report.py
│       ├── runner.py
│       └── technocore_reader.py
├── tests/
├── .gitignore
└── README.md
```

## Requirements

- Python 3.10 or newer is recommended.
- Network access is needed for live GitHub and Technocore queries.
- The current implementation uses Python's standard library for its core functionality.

## Run the mapper

From the repository root, run:

```bash
PYTHONPATH=src python -m contribution_mapper --help
```

To inspect a public repository and search the Technocore `lobby` room:

```bash
PYTHONPATH=src python -m contribution_mapper OWNER REPOSITORY \
  --room lobby \
  --output contribution-report.json
```

Replace `OWNER` and `REPOSITORY` with the GitHub repository owner and repository name you want to inspect.

For example, to inspect the Technocore DID starter repository:

```bash
PYTHONPATH=src python -m contribution_mapper zunmax technocore-did-starter \
  --room lobby \
  --output contribution-report.json
```

This example inspects a public repository; it does not imply that the repository belongs to this project's author.

Optional arguments include:

- `--artifact-url`: artifact URL to look for in retrieved messages.
- `--commit`: full Git commit SHA to look for in retrieved messages.
- `--room`: public Technocore room to inspect.
- `--output`: path for the generated JSON report.

The tool uses public information and does not require a GitHub personal access token for its public repository metadata request. Do not place private keys, access tokens, or other credentials in reports or commit them to the repository.

## Run tests

Run the unit test suite with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The initial implementation passed 38 unit tests in the development environment. Run the suite again on your own environment to confirm its current result.

## Understanding evidence

The mapper distinguishes between information it observes and conclusions that require stronger proof.

- **Verified:** reserved for evidence that has actually been verified by an appropriate method. A text match alone must not be labelled verified authorship.
- **Unverified:** observed information or a claim that has not been independently established.
- **Conflicting:** evidence sources that disagree and require investigation.
- **Unknown:** insufficient information to make a determination.

A public GitHub repository's metadata does not, by itself, prove who authored its code. Likewise, a message mentioning a repository URL or commit SHA does not establish who controlled the DID that published the message.

The current message matcher records textual references as unverified evidence. It does not independently verify a Technocore message signature, prove identity ownership, or establish Git authorship.

## Current limitations

- The mapper reads a bounded set of messages returned by the room API; it does not establish that every historical message has been examined.
- Textual matching can find useful references but cannot establish authenticity or attribution.
- The current implementation does not independently verify all cryptographic proofs associated with a contribution.
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
- Cryptographic verification of supported contribution proofs.
- More comprehensive evidence provenance and conflict handling.
- Additional tests against malformed and adversarial source data.
- Clearer report coverage information, including retrieval limits.

Roadmap items are proposals, not claims that the functionality already exists.

## License

No license has been declared yet. Until a license is added, do not assume that this repository grants permission to reuse, redistribute, or modify its code.
