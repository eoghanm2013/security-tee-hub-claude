# Vulnerability Management - Patterns

Known investigation patterns for VM (Cloud Security Vulnerabilities). Each entry captures a reusable insight from a past investigation.

---

### Scanner flags vulnerabilities from bundled lockfiles in gems (2026-03)

- **Symptoms:** Customer's Ruby image showed 130+ npm vulnerabilities in CSM despite having no npm packages installed. Vulnerabilities matched packages listed in a `yarn.lock` file bundled inside the `react_on_rails` gem.
- **Product:** VM
- **Root cause:** The SBOM scanner treats any lockfile (`yarn.lock`, `package-lock.json`, etc.) as evidence of package presence, even if the packages are not actually installed. The `react_on_rails` gem bundles its developer `yarn.lock` into the deployed gem artifact.
- **Resolution:** Two options: (1) Remove the lockfile from the image via Dockerfile (`RUN find /usr/local/bundle/gems -name "yarn.lock" -delete`), or (2) auto-mute npm vulnerabilities for affected images using Security Automation Pipelines.
- **Risk:** This pattern can affect any gem/package that bundles lockfiles for developer use. May be creating silent false positives at smaller scale for other dependencies.
- **Source:** SCRS-2019

### SBOM cannot be disabled via datadog.yaml due to env var override (2026-03)

- **Symptoms:** Customer disabled SBOM in `datadog.yaml` (`sbom.enabled: false`) but the host still reported the feature as active in Fleet Automation. Disabling `remote_updates` also did not help.
- **Product:** VM
- **Root cause:** Environment variables in `/etc/datadog-agent/environment` file were set to `DD_SBOM_ENABLED=true`, `DD_SBOM_CONTAINER_IMAGE_ENABLED=true`, `DD_SBOM_HOST_ENABLED=true`. Env vars take precedence over `datadog.yaml`. These were likely left over from a previous installation or config management tooling.
- **Resolution:** Check for env var overrides using `systemctl show datadog-agent -p Environment -p EnvironmentFiles`. Remove or set the SBOM env vars to `false` in `/etc/datadog-agent/environment`, then restart the agent.
- **Risk:** Common gotcha when hosts are reused or managed by automation that sets env vars during initial setup. Always check `envvars.log` in agent flares.
- **Source:** SCRS-2009

### False positive vulnerabilities on Windows 25H2 due to unsupported OS version (2026-02)

- **Symptoms:** Customer testing Vulnerability Management on a fully patched Windows host saw many false positive vulnerabilities. Host was running Windows build 26200 (25H2, September 2025 update).
- **Product:** VM
- **Root cause:** The VM scanner did not support Windows build 26200 (25H2). The version detection logic couldn't properly map this build to the correct vulnerability database, resulting in false positives.
- **Resolution:** Engineering merged a PR to fix Windows version detection for build 26200. After deployment, false positives dropped to only 2 remaining open vulnerabilities.
- **Risk:** New Windows builds can cause false positives until the scanner's version detection is updated. If a customer reports bulk false positives on Windows, check the OS build number against supported versions first.
- **Source:** SCRS-1945

### Stale CloudFormation trial metadata causes VM to appear enabled for Terraform-managed accounts (2026-03)

- **Symptoms:** One AWS account out of four showed Vulnerability Management (Agentless scanning) enabled in the UI despite Terraform module only configuring CSPM. Error: "Agentless scanning has been enabled but no scanner covers this account."
- **Product:** VM
- **Root cause:** The affected AWS account had a previous CloudFormation-based trial integration. When the trial was destroyed and re-integrated via Terraform, stale metadata from the CloudFormation setup persisted, causing VM to appear enabled for that account only.
- **Resolution:** Navigate to the AWS account's Configure Agentless page, choose Terraform, uncheck the VM checkbox, and click Done. This clears the stale metadata.
- **Risk:** Previous trial or CloudFormation integrations can leave residual feature flags. When a customer re-integrates an AWS account via Terraform and sees unexpected features enabled, check for prior integration history.
- **Source:** SCRS-2000
