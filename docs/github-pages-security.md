<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# GitHub Pages security boundary

The Pages deployment is a static projection. Vite is configured for the
repository base path and the application retains hash routing.

Controls:

- No runtime application API, authentication, cookies, analytics, persistence, or upload.
- `robots.txt` and HTML metadata request `noindex` for the initial direct-link release.
- HTML CSP disables network connections and limits scripts, styles, fonts, images, objects, and forms.
- Workflow build permissions are read-only; Pages and OIDC write permissions exist only in the deployment job.
- Actions are pinned to reviewed major versions or immutable revisions.

GitHub Pages does not apply a repository `_headers` file as HTTP response
headers. The portable file can document intended controls for other hosts, but
the initial deployment relies on HTML CSP and the hosting platform's controls.
