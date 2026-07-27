# Releasing EnvDoctor to PyPI

Publishing is automated with [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
(OIDC) — **no API tokens or secrets are stored anywhere.** A GitHub Release
triggers `.github/workflows/release.yml`, which builds and uploads the package.

## One-time setup (maintainer, on pypi.org)

You only do this once. It must be done by a PyPI account holder — it cannot be
automated.

1. Create a PyPI account at https://pypi.org/account/register/ (skip if you have one).
2. Go to **https://pypi.org/manage/account/publishing/** and add a
   **"pending" trusted publisher** with exactly these values:
   - **PyPI project name:** `envdoctor`
   - **Owner:** `hemanthrayuduu`
   - **Repository name:** `envdoctor`
   - **Workflow name:** `release.yml`
   - **Environment name:** `pypi`
3. (Recommended) In the GitHub repo, create an **Environment** named `pypi`
   under *Settings → Environments* so you can add release protection rules.

Because the project does not exist on PyPI yet, use the **pending** publisher
form — the project is created automatically on the first successful publish.

## Cutting a release

1. Bump `version` in `pyproject.toml` (and `__version__` in
   `envdoctor/__init__.py`) following semver.
2. Commit that on a branch and merge to `main` via PR.
3. Tag and publish a GitHub Release whose tag matches the version:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
   Then create the Release from that tag in the GitHub UI (or via the API).
4. The **Publish to PyPI** workflow runs automatically and uploads the build.

## Verify

```bash
python -m venv /tmp/envtest && /tmp/envtest/bin/pip install envdoctor
/tmp/envtest/bin/envdoctor --version
```

## Notes

- PyPI versions are **immutable**: once `0.1.0` is uploaded it can never be
  re-uploaded. Bump the version for any re-release.
- You can also trigger the workflow manually from the **Actions** tab
  (`workflow_dispatch`) once the trusted publisher is configured.
- To rehearse without touching real PyPI, configure a second trusted publisher
  on https://test.pypi.org and add a `repository-url` input to the publish step.
