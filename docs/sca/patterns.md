# SCA (Software Composition Analysis) - Patterns

Known investigation patterns for SCA. Each entry captures a reusable insight from a past investigation.

---

### Deleted/renamed repos still showing in Code Security inventory (2026-02)

- **Symptoms:** Customer renamed repos on GitHub but old names still appeared in Datadog Code Security. Deleted repos also kept reappearing after being removed from Datadog's repository settings page.
- **Product:** SCA
- **Root cause:** The 176 repos in the repository list came from scan uploads (CI/CD pipeline), not from the GitHub App integration (which only had access to 11 repos). Deleting a repo from GitHub doesn't automatically remove it from Datadog. If CI/CD pipelines continue uploading scans for old repo names, they will reappear.
- **Resolution:** Delete the repos from Security > Repository Settings in Datadog UI. Ensure CI/CD pipelines are updated to use new repo names and stop uploading scans for old names.
- **Risk:** Repos from scan uploads are independent of the GitHub App integration scope. Customers often conflate the two. If scan uploads continue with old names, repos will reappear after deletion.
- **Source:** SCRS-1940
