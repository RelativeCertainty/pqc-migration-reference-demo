# Portable PQC Reference Demo

This nested Go module is a standard-library-only delivery adapter for the PQC
reference demo. It does not replace the Cloudflare Worker or claim Cloudflare
request evidence outside Cloudflare.

From the repository root, build and validate it with:

```sh
npm run portable:check
```

The build runs Vite, stages the exact `dist/` tree with a sorted SHA-256
manifest, and produces the ignored executable at
`portable/bin/pqc-reference-demo`. A release build requires the
`portable_release` Go build tag; the npm command supplies it.

Native execution is loopback-only by default:

```sh
./portable/bin/pqc-reference-demo
```

Configuration is intentionally narrow:

- `--listen` or `PQC_DEMO_LISTEN` selects the listen address;
- `--shutdown-timeout` accepts a duration from 1 to 60 seconds; and
- `--version` prints the source/build/UI identity without host or credential
  data. It explicitly records whether the binary came from a clean commit or a
  dirty development worktree.

Containers supply `0.0.0.0:8080`; native execution defaults to
`127.0.0.1:8080`. `/healthz` and `/readyz` return fixed, identifier-free health
responses. `/api/posture` reports transport metadata as unavailable because the
portable process does not terminate or inspect upstream TLS and deliberately
ignores forwarding headers.
