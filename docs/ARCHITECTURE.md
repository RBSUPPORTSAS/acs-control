# ACS Control - Architecture

## Overview

ACS Control is a management layer built on top of GenieACS.

Its purpose is to provide a normalized and safe interface for managing TR-069 devices while hiding vendor-specific complexity from users, external applications and automation agents.

Main components:

- FastAPI backend
- Vue 3 frontend
- PostgreSQL
- Redis
- GenieACS integration through the NBI API

## High-level architecture

```text
Browser / External Client / Automation Agent
                    |
                    | REST API
                    v
              ACS Control
           FastAPI + Vue 3
                    |
          +---------+--------+
          |                  |
          v                  v
     PostgreSQL            Redis
                    |
                    v
               GenieACS NBI
                    |
                    | TR-069
                    v
                 ONU / CPE
```

The frontend and external systems should communicate with ACS Control, not directly with GenieACS.

ACS Control is responsible for validation, normalization, vendor compatibility and protection of sensitive management operations.

## Project structure

### Backend

Main location:

```text
backend/
```

Important files and directories:

```text
backend/app/main.py                 FastAPI application and API routes
backend/app/core/config.py          Application configuration
backend/app/core/database.py        PostgreSQL connection
backend/app/models/                 Database models
backend/app/services/               Business logic and GenieACS integration
backend/requirements.txt            Known-good Python dependencies
backend/requirements.in             Direct Python dependencies
```

The backend contains all safety checks and vendor-specific logic.

### Frontend

Main location:

```text
frontend/
```

Important files:

```text
frontend/src/main.js                Main Vue application
frontend/src/style.css              Application styles
frontend/package.json               Frontend dependencies and scripts
frontend/package-lock.json          Reproducible dependency lock file
```

The frontend consumes the ACS Control REST API and should not communicate directly with GenieACS.

## GenieACS integration

ACS Control communicates with GenieACS through its NBI API.

The connection is configured with:

```env
GENIEACS_NBI_URL=http://GENIEACS_HOST:7557
```

The main integration service is:

```text
backend/app/services/genieacs.py
```

External systems should preferably integrate with ACS Control instead of sending GenieACS tasks directly.

This allows ACS Control to apply validation, compatibility checks, auditing and protection rules before a change reaches a device.

## Device normalization

Raw GenieACS device data is normalized before being used by higher-level features.

The normalization logic is located in:

```text
backend/app/services/device_normalizer.py
```

A normalized device can expose fields such as:

```text
id
serial_number
manufacturer
product_class
software_version
hardware_version
oui
tags
online
last_inform
```

The goal is to keep the API consistent even when different vendors expose different TR-069 parameter trees.

## WAN management

WAN behavior may differ between vendors and models.

Relevant services include:

```text
backend/app/services/wan_reader.py
backend/app/services/wan_builder.py
backend/app/services/wan_create.py
backend/app/services/wan_capabilities.py
backend/app/services/vsol_wan_builder.py
backend/app/services/vsol_wan_creator.py
backend/app/services/interface_inventory.py
```

### Critical TR-069 protection rule

Any WAN whose ServiceList contains TR069 must be considered protected.

Examples:

```text
TR069
TR069_INTERNET
TR069_VOIP
```

Normal WAN edit or delete operations must never break the TR-069 management path.

Vendor-specific WAN structures must not be assumed to be identical.

## Wi-Fi management

Relevant services:

```text
backend/app/services/wifi_reader.py
backend/app/services/wifi_writer.py
backend/app/services/wifi_capabilities.py
backend/app/services/wlan_inventory.py
```

Wi-Fi instance indexes may differ between vendors and models.

Do not assume that the same WLANConfiguration instance represents the same band on every device.

Passwords must never be returned in clear text through the public API.

## CATV management

CATV support must be detected per device before write operations are attempted.

CATV operations should validate support, resolve the correct writable TR-069 parameter, apply the change through GenieACS and record the operation in the audit log.

## Security module

The security module manages supported firewall and management-service parameters exposed by the CPE.

Relevant service:

```text
backend/app/services/security_module.py
```

Current safety rules include:

- Do not enable WAN management services when the device firewall policy does not allow it.
- Existing WAN services may be disabled even when the firewall is restrictive.
- TR-069 management itself must not be modified through normal security operations.

Examples of managed services may include HTTP, HTTPS, SSH, Telnet, FTP, TFTP and ICMP depending on device support.

## Audit

Relevant files:

```text
backend/app/models/audit.py
backend/app/services/audit_service.py
```

Write operations should be auditable.

Future external integrations should include a correlation or request ID so changes made by agents, scripts or external systems can be traced end to end.

## External agents and automation

Automation agents should consume ACS Control APIs instead of constructing GenieACS tasks directly.

Preferred flow:

```text
Agent
  |
  | Intent
  v
ACS Control API
  |
  | Validation / permissions / compatibility
  v
GenieACS
  |
  v
Device
```

Future API security should include:

- API keys or JWT
- Scopes and permissions
- Request IDs
- Rate limiting
- Idempotency controls
- Audit identity

## Adding support for a new vendor or model

Do not modify existing vendor logic blindly.

Recommended process:

1. Identify manufacturer, model and firmware.
2. Inspect the TR-069 parameter tree.
3. Identify readable and writable parameters.
4. Detect model capabilities before enabling write operations.
5. Add vendor-specific logic only where required.
6. Preserve the normalized ACS Control API contract.
7. Protect TR-069 management connectivity.
8. Test read operations first.
9. Test write operations on a controlled device.
10. Document the new implementation.

Vendor-specific behavior should remain isolated whenever possible.

New vendor support should prefer capability-based detection over assumptions based only on manufacturer names.

## Development principles

- Safety checks belong in the backend, not only in the frontend.
- Do not expose device passwords in clear text.
- Do not expose private infrastructure details in source code.
- Do not bypass ACS Control protections by sending raw GenieACS tasks from higher-level features.
- Preserve backward compatibility whenever practical.
- Keep vendor-specific logic separated from normalized API behavior.
- Write auditable operations for configuration changes.

## Planned architecture

Major planned components include:

- Templates
- Bulk operations with pre-validation
- Multi-GenieACS support
- API authentication
- Roles and permissions
- External agent integration
- Diagnostics
- Expanded vendor capability detection
- Automated testing

ACS Control should continue evolving as a normalized and safe management layer on top of GenieACS.
