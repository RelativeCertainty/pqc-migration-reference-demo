# Security Policy

## Reporting a vulnerability

Please use GitHub's private vulnerability-reporting feature for this
repository. Do not place credentials, personal data, customer data, private
infrastructure details, or exploit payloads in a public issue.

## Scope and boundaries

This repository is a source-only, synthetic portfolio project. It does not
assert a live public deployment or production security boundary. The included
Worker and Go adapters expose read-only application routes, use no application
data store, and are designed not to echo request bodies, cookies, identity, or
source addresses.

Do not use this project to process real inventory or sensitive evidence without
an independent security, privacy, authorization, retention, deployment, and
operational review.
