# Core Contracts CI Runner

## Assignment

`ha-platform/core-contracts` uses the project runner `core-contracts-ci`.
The runner is locked to GitLab project 22 and accepts only jobs carrying the
`core-contracts-ci` tag.

| Property | Value |
| --- | --- |
| GitLab runner ID | `2` |
| Runtime location | Proxmox LXC 122 (`gitlab`) |
| LXC resources | 4 vCPU, 10 GiB RAM, 2 GiB swap, 80 GiB root disk |
| LXC properties | Debian 12, unprivileged, nesting enabled, autostart enabled |
| Runner version | 19.2.0 |
| Executor | Docker |
| Default image | `python:3.13-slim` |
| Required job tag | `core-contracts-ci` |
| Project lock | enabled |
| Run untagged | disabled |
| Access level | unprotected and protected refs |
| Maximum job timeout | 900 seconds |

The Docker executor is not privileged. No Home Assistant mount, production
secret mount, GitLab API token, or GitHub mirror token is exposed to test
containers. Release credentials remain protected GitLab CI variables and are
available only under the rules of the central release job.

The existing media release runner is not assigned to `core-contracts`. The
project runner remains available for the repository's existing optional CI and
release jobs; a successful pipeline is not a merge, release, or acceptance
requirement for Core Contracts.

## Health check

The expected healthy state is:

- LXC 122 is running and starts with the Proxmox host.
- `docker.service` and `gitlab-runner.service` are active and enabled.
- GitLab runner 2 reports `online`, `paused=false`, `locked=true`,
  `run_untagged=false`, and tag `core-contracts-ci`.
- Project 22 lists runner 2 as its only project runner.

Use `gitlab-runner verify` inside LXC 122 for a local connectivity check.
Use the GitLab Runners API for the authoritative project assignment and
online status.

## Recovery and re-registration

Do not reuse another project's runner or a legacy registration token.

1. Restore network and the `docker` and `gitlab-runner` services in LXC 122.
2. Run `gitlab-runner verify`.
3. If the runner authentication is irrecoverable, delete only runner 2 from
   GitLab, create a new project runner through `POST /user/runners`, and
   register it with the one-time authentication token.
4. Reapply the properties in the assignment table and confirm the project
   lists no foreign runner.
5. If a pipeline is needed for an independent diagnostic or release check,
   observe it separately. Do not make it a prerequisite for merging or
   accepting Core Contracts work.

Runner authentication tokens must never be committed, printed in job logs, or
stored in repository files.
