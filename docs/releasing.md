# Publishing a release

The official PowerContract repository uses GitHub Actions and PyPI Trusted Publishing. No long-lived PyPI API token is stored in GitHub.

The PyPI publisher and GitHub `pypi` environment are already configured for the Sidelobe repository.

## Normal release

Prepare a release pull request:

1. update `src/powercontract/__init__.py` to the new version;
2. add the release to `CHANGELOG.md`;
3. confirm that the pull request CI is green;
4. merge those changes to the default branch.

Merging a change to `src/powercontract/__init__.py` into `main` starts the **Release** workflow automatically. The merge is the publishing step; no separate tag push or manual workflow run is needed.

The workflow can also be started manually from the default branch when its current version has not yet been tagged:

1. open **Actions** on GitHub;
2. select **Release**;
3. choose **Run workflow**;
4. run it from the default branch.

The workflow reads the version from the built wheel. You do not type the version into the Actions form.

For example, if the package version is `0.1.3`, the workflow creates tag `v0.1.3`.

Before creating the tag it:

1. runs the test suite;
2. runs both bundled CLI examples;
3. builds the wheel and sdist;
4. runs `twine check`;
5. installs the built wheel and reads its version;
6. checks that the tag does not already exist.

If those checks pass, the same workflow:

1. creates and pushes the annotated version tag;
2. creates the GitHub Release;
3. attaches the wheel, sdist, and SHA-256 checksums;
4. publishes the same wheel and sdist to PyPI through OIDC.

If the current version already has a release tag, the workflow stops instead of overwriting it.

The workflow only runs releases from the default branch. Pushing a tag does not start it; let the workflow create the annotated tag after its checks pass.

## PyPI authentication

The publish job uses:

```yaml
environment: pypi
permissions:
  id-token: write
```

with:

```text
pypa/gh-action-pypi-publish@release/v1
```

PyPI exchanges the GitHub OIDC identity for a short-lived publishing credential. There is no `PYPI_TOKEN` repository secret.

## Initial Trusted Publishing setup

These values are recorded here for maintenance, forks, or disaster recovery:

```text
PyPI project name: powercontract
Owner:             sidelobe-labs
Repository:        powercontract
Workflow name:     release.yml
Environment name:  pypi
```

The GitHub Actions environment must also be named `pypi`.

## After publishing

Check the release from a clean environment:

```bash
python -m pip install --upgrade powercontract
powercontract --version
```

Also check:

- the GitHub Release contains the wheel, sdist, and `SHA256SUMS`;
- PyPI shows the expected version;
- the package page renders the README correctly.

PyPI stores the README and project metadata from each uploaded distribution. Editing `README.md` on GitHub does not change the page for an already-published version; the updated README appears with the next package release.

## If publishing fails

Do not delete or move a release tag until the failure is understood.

For Trusted Publishing failures, compare the PyPI publisher configuration with:

- owner;
- repository;
- workflow filename;
- environment name;
- package/project name.

They must match the workflow exactly.

If a tag was created but the PyPI upload failed, fix the publishing configuration before doing anything with the version. Do not upload a different build under the same version.
