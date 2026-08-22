# Security Policy

ACS Control manages network devices and may execute configuration changes that affect customer connectivity.

## Sensitive information

Never include in Issues, Pull Requests or commits:

- Production credentials
- Real .env files
- API tokens or private keys
- Customer information
- Device configuration exports containing secrets
- Production infrastructure details that are not required to reproduce a problem

## Reporting vulnerabilities

Do not publish exploitable security vulnerabilities as a public Issue.

Contact the repository maintainers privately through the security reporting mechanisms available on GitHub.

## High-risk areas

Extra review is required for WAN deletion, VLAN changes, PPPoE credentials, TR-069 management paths, firewall changes, bulk operations and authentication changes.

Backend safety controls must never be removed merely to make a device operation succeed.
