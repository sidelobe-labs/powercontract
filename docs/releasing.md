# Publishing a release

PowerContract uses GitHub Actions and PyPI Trusted Publishing. No long-lived PyPI API token is stored in GitHub.

## One-time PyPI setup

Sign in to PyPI and open:

```text
Account settings -> Publishing
```

Create a pending GitHub publisher with these values:

```text
PyPI project name: powercontract
Owner:             sidelobe-labs
Repository:        powercontract
Workflow name:     release.yml
Environment name:  pypi
```

The PyPI project does not need to exist first. A pending publisher creates it on the first successful upload.

Important: a pending publisher does not reserve the project name. Do not create it days in advance and assume the name is held.

The project name must match the package metadata exactly:

```toml
name = "powercontract"
```

## GitHub environment

Create a GitHub Actions environment named:

```text
pypi
```

The release workflow refers to that exact environment name.

If your GitHub plan supports deployment protection rules for the repository, requiring approval for this environment is a useful extra safeguard. It is not required by PowerContract itself.

## Release flow

The release workflow runs on tags matching:

```text
v[0-9]*
```

For v0.1.0:

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m "PowerContract v0.1.0"
git push origin v0.1.0
```

The workflow then:

1. builds the sdist and wheel once;
2. runs `twine check`;
3. installs the wheel and checks that the package version matches the tag;
4. stores the built distributions as a workflow artifact;
5. creates the GitHub Release and attaches the distributions plus `SHA256SUMS`;
6. publishes the same wheel and sdist to PyPI through OIDC.

The PyPI job has `id-token: write` and uses the official `pypa/gh-action-pypi-publish` action. There is no `PYPI_TOKEN` secret.

## Before pushing the tag

Check:

```bash
git status
git log -1 --oneline
```

Then confirm on GitHub that the latest `main` CI run is green.

Also confirm that:

- the PyPI pending publisher uses `release.yml`;
- the PyPI publisher environment is `pypi`;
- the GitHub environment is also named `pypi`;
- the version in `src/powercontract/__init__.py` matches the tag.

## If the PyPI publish fails

Do not move or recreate the existing tag until the failure is understood.

Common Trusted Publishing failures are mismatched values between PyPI and GitHub:

- wrong repository owner;
- wrong repository name;
- wrong workflow filename;
- wrong environment name;
- project name does not match package metadata.

PyPI's publisher configuration and the GitHub workflow must match exactly.
