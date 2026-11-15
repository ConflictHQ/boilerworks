# boilerworks new

Create an app on the Calliope AI happy path: a supported template, deployed on Astrolift, with its
Storybook as a section of the [Calliope AI UX front door](https://github.com/calliopeai/calliope-ux).

```bash
boilerworks new <template> <project> [options]
boilerworks new django-nextjs acme-portal --name "Acme Portal" --repo acme/acme-portal
```

## Supported templates

| Template | Backend manifest | Web manifest | Storybook manifest |
|----------|------------------|--------------|--------------------|
| `nestjs-nextjs` | `astrolift.toml` | `apps/web/astrolift.toml` | `storybook/astrolift.toml` |
| `django-nextjs` | `astrolift.toml` | `frontend/astrolift.toml` | `storybook/astrolift.toml` |
| `fastapi-nextjs` | `astrolift.toml` | `frontend/astrolift.toml` | `storybook/astrolift.toml` |

Each depends on `@calliopelabs/ui`, defines its product in `<web>/ui-app/product.ts`, and ships a
Storybook with a11y gates. Astrolift builds one image per app, so each template has three apps.
For any other template, use [`setup`](setup.md) and [`init`](init.md).

## Options

| Option | Description |
|--------|-------------|
| `--name TEXT` | Product name (default: from the slug, `acme-portal` becomes `Acme Portal`) |
| `--repo OWNER/NAME` | The new app's GitHub repo. Written to the manifests; needed by `--register` and `--catalog` |
| `--output PATH` | Where to create the project directory (default: `.`) |
| `--dry-run` | Print the plan, the renames, and (with the flags below) the commands and catalog entry; write nothing |
| `--register / --no-register` | Register the three apps with the Astrolift CLI. Without either flag, `new` asks when run in a terminal and skips otherwise |
| `--project-id GUID` | The Astrolift project to register the apps under (required with `--register`) |
| `--manifest-raw` | Send the local manifests with the registration, for a repo the platform cannot read yet |
| `--catalog print\|pr\|skip` | Print the front door `catalogs.json` entry, or open it as a PR on calliopeai/calliope-ux with `gh`. Without the flag, `new` asks in a terminal and skips otherwise |

Nothing is registered and no PR is opened unless you pass the flag or answer yes. Without `--repo`,
neither is offered, because both name the repo the manifests were rendered with.

## What it does

1. Clones the template, removes its `.git/`, and renames it like [`init`](init.md) does.
2. Renames the placeholder slugs everywhere (manifests, managed service names, README):

    | Placeholder | Becomes |
    |-------------|---------|
    | `boilerworks-app` | `<project>` (the backend app; services `<project>-db`, `<project>-redis`) |
    | `boilerworks-app-web` | `<project>-web` |
    | `storybook-boilerworks-app` | `storybook-<project>` |
    | `ConflictHQ/boilerworks-<template>` | the `--repo` value |

3. Sets each manifest's `display_name` (`<name>`, `<name> Web`, `<name> Storybook`) and the
   product's `id` (the slug) and `name` in `ui-app/product.ts`.
4. Runs `git init` with an initial commit.
5. With `--register`, from the project root, for each manifest:

    ```bash
    astro app register -f <manifest> --manifest-path <manifest> \
      --project-id <guid> --source-repo <owner/name> --yes [--manifest-raw]
    ```

    The `astro` CLI must be installed and logged in. Without `--manifest-raw` the platform reads
    the manifests from the repo, so push the project first. Registration stops at the first
    failure. Then create the backend's secrets, listed at the top of its `astrolift.toml`
    (`astro app secrets create <KEY> <project> --stdin`).

6. With `--catalog print`, prints the front door entry; with `--catalog pr`, clones
   calliopeai/calliope-ux, appends it to `catalogs.json` on a `catalog/<project>` branch and opens
   a PR (needs `gh auth login` and push access). An id or app already in the catalog is refused.

```json
{
  "id": "acme-portal",
  "title": "Acme Portal",
  "group": "web",
  "kind": "storybook",
  "repo": "acme/acme-portal",
  "app": "storybook-acme-portal",
  "upstream": "web.conflict-storybook-acme-portal.svc.cluster.local:8080"
}
```

`upstream` is `<workload>.conflict-<app slug>.svc.cluster.local:8080`; the Storybook's workload is
`web`. Merge the PR once the Storybook app is deployed on the cluster.

## The whole path

```bash
boilerworks new nestjs-nextjs acme-portal --repo acme/acme-portal
cd acme-portal
gh repo create acme/acme-portal --private --source . --push
cd ..
boilerworks new nestjs-nextjs acme-portal --repo acme/acme-portal --dry-run \
  --register --project-id <guid> --catalog print     # prints the astro commands and the entry to run yourself
```

Or in one go, registering from the local manifests and opening the front door PR:

```bash
boilerworks new nestjs-nextjs acme-portal --repo acme/acme-portal \
  --register --project-id <guid> --manifest-raw --catalog pr
```

Pushes to `main` then deploy through the managed workflow, and Dependabot's `@calliopelabs`
group brings library upgrades.
