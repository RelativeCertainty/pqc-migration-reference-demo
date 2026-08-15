# Third-Party Notices

This repository does not vendor its npm dependencies. Packages installed by
`npm ci` remain subject to their respective licenses; `package-lock.json` is
the authoritative resolved dependency inventory.

Direct runtime dependencies:

- React
- React DOM

Development and validation dependencies include Cloudflare Workers types and
Wrangler, Vite, Vitest, TypeScript, ESLint, Testing Library, jsdom, and related
type packages. Their license metadata is recorded in the npm lockfile and
installed package manifests.

The portable Go module uses only the Go standard library. Python validation
uses pytest, jsonschema, and referencing under their respective licenses.

References to NIST publications and other external documentation are citations
to those sources, not copies of or ownership claims over them.
