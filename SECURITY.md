# Security policy

## Reporting a vulnerability

**Do not open a public issue.** Write to <contact@planvortex.com> with the details and, if you can,
a way to reproduce it. You will get an answer within a few working days.

Please include the package version, the Python version, whether you hit it on the synchronous or
the asynchronous client, and whether the problem is in this client or in the PlanVortex API behind
it.

## What is in scope

This package is a client. Vulnerabilities in it typically look like: a secret being logged or
included in an error, a webhook signature that can be forged or bypassed, or a request being sent
somewhere other than the configured `base_url`.

## A note on where your secret lives

This is a server-side package. The `client_credentials` flow needs your `client_secret`, and
putting it anywhere a browser can read hands over the account. Python has no browser to guard
against, so the package cannot stop you — the temporal connect token is the piece meant for the
browser side of the flow, and it is what your front end should receive.

## Supported versions

The latest published minor version receives security fixes.
