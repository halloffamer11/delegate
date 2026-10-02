# 14 — A Kiro relay in the delegate-skills fork

**What to build:** a `skills/kiro-delegate/` relay in `halloffamer11/delegate-skills` with the same `delegate-relay.result.v1` contract as the other 17, offered upstream. Kiro headless, per kiro.dev docs read 2026-10-02: `kiro-cli chat --no-interactive --agent <a> --trust-tools=<categories> --output-format stream-json`, `KIRO_API_KEY` required (Pro tier and up); models list with `kiro-cli chat --list-models --format json`. Not found in the docs: a headless model flag (model comes from the agent config or `chat.defaultModel`) and any usage or credits command. The relay copies the shared symbols the parity test checks.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] `relay.mjs` maps `--read-only` to the narrowest trusted tool set and adds the git-fingerprint tripwire if that is weak.
- [ ] `test/relay-parity.mjs` and a fake-CLI suite pass in the fork.
- [ ] `ads.sh` pins the new commit; the upstream PR link is recorded here.
- [ ] One live read-only run on Orin's machine with his API key (Orin's box).
