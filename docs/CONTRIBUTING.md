# Contributing to ACS Control

Thank you for contributing to ACS Control.

ACS Control is a management and automation layer built on top of GenieACS for TR-069 devices.

Contributions are welcome from developers, network engineers, device vendors and automation agents.

## Before contributing

Please understand these project rules before modifying the code:

- Do not commit real credentials or production .env files.
- Do not commit real device exports, configuration backups or customer data.
- Do not hardcode private infrastructure addresses.
- Do not bypass backend safety checks.
- Do not break TR-069 management connectivity.
- Do not assume all vendors expose the same TR-069 structure.
- Test read operations before write operations.
- Keep vendor-specific behavior isolated whenever possible.

The backend is the authoritative place for safety validation.

## Development workflow

Use a dedicated branch for every change.

Recommended flow:

```bash
git checkout -b feature/short-description
```

Make the change, test it locally, then review the diff:

```bash
git diff
git status
```

Commit with a clear message:

```bash
git add .
git commit -m "feat: add short description"
```

Push the branch:

```bash
git push -u origin feature/short-description
```

Then open a Pull Request against the main branch.

## Commit message examples

```text
feat: add support for a new ONU model
fix: protect TR069 WAN from deletion
docs: update API integration guide
refactor: isolate vendor-specific Wi-Fi logic
test: add WAN capability validation
```

Pull Requests should explain what changed, why it changed, how it was tested and whether the change affects device write operations.

## Vendor and TR-069 contribution rules

Support for new vendors or models must be added carefully.

Before implementing write operations:

1. Capture the device manufacturer, model and firmware.
2. Inspect the TR-069 tree from GenieACS.
3. Identify the exact readable and writable parameters.
4. Confirm whether paths differ between firmware versions.
5. Add capability detection before enabling features.
6. Keep vendor-specific code isolated from generic API behavior.
7. Preserve existing behavior for already-supported devices.

### TR-069 management protection

Never delete, disable or modify a WAN path that is required for ACS management.

If ServiceList contains TR069, the WAN must be treated as protected.

Examples:

```text
TR069
TR069_INTERNET
TR069_VOIP
```

Do not expose generic delete or edit functions that can bypass this protection.

### Wi-Fi

Do not assume WLAN instance numbers are universal.

The same WLANConfiguration index may represent different bands on different vendors or models.

### WAN

Do not assume all vendors use the same WANConnectionDevice layout.

WAN creation, editing and deletion must use vendor capabilities and validated object structure.

### CATV

Do not assume CATV exists or uses the same parameter path on every device.

Detect support and writable parameters before offering CATV control.

## AI agent contribution rules

AI coding agents are welcome to analyze, document and contribute to ACS Control.

However, automated changes must follow the same safety rules as human contributions.

### Before changing code

An AI agent should first inspect:

- docs/ARCHITECTURE.md
- docs/CONTRIBUTING.md
- backend/app/main.py
- relevant files under backend/app/services/
- existing vendor-specific logic

The agent should understand the current behavior before replacing or refactoring working code.

### Required behavior

AI-generated changes must:

- preserve TR-069 management connectivity;
- preserve existing vendor support;
- keep safety validation in the backend;
- avoid exposing secrets or device passwords;
- avoid hardcoding production IP addresses or credentials;
- avoid assuming vendor parameter trees are identical;
- prefer capability detection over manufacturer-only assumptions;
- document new API endpoints and configuration variables;
- include a clear explanation of what was changed;
- identify any write operation that can affect customer connectivity.

### High-risk changes

Changes involving the following areas require additional review and controlled testing:

- WAN creation or deletion
- PPPoE credentials
- VLAN changes
- TR-069 paths
- Firewall rules
- Remote management services
- Bulk operations
- Template application
- Factory reset or reboot operations

An AI agent must not remove existing safety checks merely to make an operation succeed.

### Preferred development approach

When adding device support, prefer:

```text
Capability detection
        |
        v
Normalized ACS Control operation
        |
        v
Vendor-specific implementation
        |
        v
GenieACS
```

This keeps external API consumers independent from vendor-specific TR-069 paths.

## Minimum testing requirements

Every Pull Request should include appropriate testing for the affected area.

### Backend changes

At minimum:

```bash
python -m py_compile backend/app/main.py
```

For service changes, compile the modified modules as well.

The backend should also be importable with a test configuration.

Example:

```bash
APP_SECRET_KEY=test \
GENIEACS_NBI_URL=http://127.0.0.1:7557 \
DATABASE_URL=postgresql+asyncpg://test:test@127.0.0.1:5432/test \
PYTHONPATH=backend \
python -c "from app.main import app; print(app.title)"
```

### Frontend changes

At minimum:

```bash
cd frontend
npm ci
npm run build
```

The build must complete without errors.

### Device read operations

Validate that existing device inventory and read endpoints continue to work.

### Device write operations

Write operations must be tested only on controlled devices.

Verify both success and safety behavior.

Examples:

- supported device accepts the change;
- unsupported device is rejected safely;
- protected TR-069 WAN cannot be modified or deleted;
- invalid parameters return a controlled API error;
- audit information is recorded when applicable.

### Regression testing

A change for one vendor must not silently break another supported vendor.

If the change affects shared logic, test at least one device from each supported implementation when possible.

### Pull Request checklist

Before requesting review, confirm:

- [ ] No secrets were committed
- [ ] No production IP addresses were hardcoded
- [ ] Backend safety checks remain active
- [ ] Frontend builds successfully
- [ ] Backend imports successfully
- [ ] Existing supported devices were considered
- [ ] New write operations were tested on a controlled device
- [ ] Documentation was updated when behavior changed
- [ ] API changes were documented
- [ ] High-risk changes were clearly identified
