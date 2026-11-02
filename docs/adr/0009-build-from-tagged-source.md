# ADR 0009: VM builds and runs the tagged source with docker compose

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** @MohammedAlkahali (release), team
- **Related:** #18, #19, #56

## Context
The VM must run release `v0.1.0`, built from source with docker compose. No image registry may be used, and anyone must be able to run the system from a fresh clone.

## Options considered
1. **Push images to a registry and pull them on the VM**: the brief forbids this.
2. **Check out the tag on the VM and run `docker compose up -d --build`.**

## Decision
- **Deploy:** `git fetch --tags && git checkout vX.Y.Z && docker compose up -d --build`.
- **Roll back:** check out the previous tag and run the same command.
- The named database volume is kept across deploys and rollbacks.

## Consequences
- The VM needs only Git, Docker and a `.env` file, and every step is written in the README.
- What runs in production is exactly the tagged source.
