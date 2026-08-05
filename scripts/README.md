# `scripts/` — developer tooling

Things you run by hand. Nothing here is part of the deployed accelerator.

## What's here

| Path | What it does |
|---|---|
| `new-accelerator.sh` | Clones this repo into a fresh, re-pointed, git-initialised accelerator |
| `example.py` | Smallest possible demo of the AI layer — text in, URLs out |

## Start a new accelerator

```bash
make new VERTICAL=healthcare USECASE=readmission-risk
```

Creates `../cloudera-forge-healthcare-readmission-risk/` as a sibling directory:
copies the template, rewrites the accelerator name through the docs and Makefile,
clears T2URL's worked example out of the layer directories while keeping their
`README.md` guidance, and initialises a fresh git repo with one commit.

It refuses to overwrite an existing directory. Pass `--dry-run` to see the plan
first.

## Try the library

```bash
python scripts/example.py
```

Three lines of real usage against the AI layer. This hits a live search engine —
it is the fastest way to confirm the accelerator works end to end without starting
the server.

## Conventions

- **Nothing here ships.** Deployment scripts live in [`.cicd/`](../.cicd/),
  provisioning in [`infra/`](../infra/). If it runs in production it is in the wrong
  directory.
- **Dry run by default for anything destructive.** `new-accelerator.sh` writes to a
  new directory and refuses to clobber, but still supports `--dry-run` because the
  first thing anyone wants is to see what it will do.
- **POSIX shell, no dependencies.** These run on a laptop before anything is
  installed. `example.py` needs only `ai/requirements.txt`.
