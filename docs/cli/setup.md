# boilerworks setup

Run the interactive setup wizard. Asks questions about your project and writes `boilerworks.yaml`.

```bash
boilerworks setup
boilerworks setup --output /path/to/boilerworks.yaml
```

## Options

| Option | Description |
|--------|-------------|
| `--output PATH` | Where to write the manifest (default: `boilerworks.yaml` in cwd) |

## Questions

The wizard walks through 13 steps:

1. **Project name** — validated slug (lowercase, letters/digits/hyphens, must start with a letter)
2. **Template size** — Full / Micro / Edge (with a guide panel)
3. **Template family** — filtered by size, shown as a Rich table with status indicators
4. **Topology** — standard, omni, or api-only (filtered to what the template supports)
5. **Cloud provider** — aws / gcp / azure / none
6. **Infrastructure** — include boilerworks-opscode? (shown only if cloud is selected)
7. **Region** — default varies by cloud
8. **Domain** — optional
9. **Mobile** — include mobile template? (Full templates only)
10. **Web presence** — include marketing site? (Full templates only)
11. **Compliance** — multi-select: soc2, hipaa, pci-dss, gdpr
12. **Email provider** — ses / sendgrid / mailgun / none
13. **E2E testing** — playwright / cypress / none

A summary panel shows all selections before writing.

## Output

```yaml
# boilerworks.yaml
project: my-app
family: django-nextjs
size: full
topology: standard
cloud: aws
ops: true
region: us-east-1
domain: myapp.com
...
```

Pass this file to `boilerworks init` to generate the project.
