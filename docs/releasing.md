# Publishing a release

PowerContract uses GitHub Actions and PyPI Trusted Publishing. No long-lived PyPI API token is stored in GitHub.

## One-time setup

### PyPI

Sign in to PyPI and open:

```text
Account settings -> Publishing
```

Create a pending GitHub publisher with:

```text
PyPI project name: powercontract
Owner:             sidelobe-labs
Repository:        powercontract
Workflow name:     release.yml
Environment name:  pypi
```

The project does not need to exist first. A pending publisher can create it on the first successful upload.

A pending publisher does not reserve the project name before that first upload.

### GitHub

Create an Actions environment named:

```text
pypi
```

The environment name must match the PyPI publisher configuration exactly.

If the repository plan supports environment approval rules, requiring approval before the `pypi` job is a useful safeguard.

## Normal release: one click

Once the PyPI publisher and GitHub environment are configured:

1. Open the repository on GitHub.
2. Open **Actions**.
3. Select **Release**.
4. Choose **Run workflow**.
5. Run it from the default branch.

The workflow reads the version from the built package. For version `0.1.0`, it creates tag `v0.1.0`.

Before creating the tag it:

1. installs the development dependencies;
2. runs the test suite;
3. runs both bundled CLI examples;
4. builds the wheel and sdist;
5. runs `twine check`;
6. installs the built wheel and reads its version;
7. checks that the tag does not already exist.

If those checks pass, the same workflow:

1. creates and pushes the annotated version tag;
2. uploads the wheel and sdist as a workflow artifact;
3. creates the GitHub Release;
4. adds SHA-256 checksums;
5. publishes the same wheel and sdist to PyPI through OIDC.

No version number is entered in the Actions form. The package version remains the source of truth.

## Tag-triggered release

The workflow still accepts a manually pushed tag matching:

```text
v[0-9]*
```

When started by a tag, it verifies that the tag matches the version read from the built wheel before releasing anything.

This is useful for maintainers who prefer the normal Git tag flow, but it is not required for routine releases.

## Why the manual workflow can create a tag safely

The one-click run pushes the tag with the repository's `GITHUB_TOKEN`.

GitHub does not start another workflow run for ordinary push events created with that token, so the generated tag does not recursively start a second Release workflow. The current workflow continues and creates the release itself.

## PyPI authentication

The `pypi` job has:

```yaml
environment: pypi
permissions:
  id-token: write
```

and uses:

```text
pypa/gh-action-pypi-publish@release/v1
```

PyPI exchanges the GitHub OIDC identity for a short-lived publishing credential. There is no `PYPI_TOKEN` repository secret.

## Before the first release

Confirm that:

- the pending PyPI publisher uses project name `powercontract`;
- owner is `sidelobe-labs`;
- repository is `powercontract`;
- workflow filename is `release.yml`;
- environment is `pypi`;
- the GitHub Actions environment is also named `pypi`;
- the latest CI run on the default branch is green.

Then use **Actions -> Release -> Run workflow**.

## If publishing fails

Do not delete or move a release tag until the failure is understood.

For Trusted Publishing, first compare the PyPI publisher values with the workflow:

- owner;
- repository;
- workflow filename;
- environment name;
- package/project name.

They must match exactly.

If the tag was created but PyPI upload failed, fix the publishing configuration first. Do not reuse the version number for a different build.
