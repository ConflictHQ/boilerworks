# boilerworks init

Generate a project from a `boilerworks.yaml` manifest.

```bash
boilerworks init
boilerworks init --manifest path/to/boilerworks.yaml
boilerworks init --output ~/repos/
boilerworks init --dry-run
```

## Options

| Option | Description |
|--------|-------------|
| `--manifest PATH` | Manifest file to read (default: `boilerworks.yaml` in cwd) |
| `--output PATH` | Where to create the project directory (default: `.`) |
| `--dry-run` | Print what would happen without touching the filesystem |

## What it does

1. Reads and validates `boilerworks.yaml`
2. Clones `ConflictHQ/boilerworks-{family}` → `{output}/{project}/`
3. Removes `.git/` from the clone
4. Runs string replacement across all text files: `boilerworks` → `{project}` (3 case variants)
5. Renames files and directories containing `boilerworks`
6. If `ops: true` and `cloud` is set:
    - Clones `ConflictHQ/boilerworks-opscode`
    - Standard topology: places it at `{output}/{project}-ops/`
    - Omni topology: places it at `{output}/{project}/ops/`
    - Writes `{cloud}/config.env` with project name, region, domain
7. Runs `git init` + initial commit

## Clone auth

The CLI tries SSH first, then HTTPS:

```
git@github.com:ConflictHQ/boilerworks-{family}.git   ← tried first
https://github.com/ConflictHQ/boilerworks-{family}.git  ← fallback
```

## Dry run example

```bash
boilerworks init --dry-run

  1. Clone ConflictHQ/boilerworks-django-nextjs
  2. Remove .git/ from cloned directory
  3. Replace all 'boilerworks' → 'my-app' (case-variant)
  4. Rename files/dirs containing 'boilerworks'
  5. Update CLAUDE.md and README.md headers
  6. git init + initial commit in /Users/me/repos/my-app
  7. Clone ConflictHQ/boilerworks-opscode → /Users/me/repos/my-app-ops
  8. Render + rename ops files (boilerworks → my-app)
  9. Write aws/config.env (project, region, domain)
  10. git init ops repo in /Users/me/repos/my-app-ops

Output directory: /Users/me/repos/my-app
```
