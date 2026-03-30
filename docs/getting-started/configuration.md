# Configuration

## boilerworks.yaml

The manifest file that drives `boilerworks init`. Created by `boilerworks setup`, or write it by hand.

```yaml
project: my-app
family: django-nextjs
size: full
topology: standard
cloud: aws
ops: true
region: us-east-1
domain: myapp.com
mobile: false
web_presence: false
compliance:
  - soc2
services:
  email: ses
  storage: null
  search: null
  cache: redis
data:
  database: postgres
  migrations: true
  seed_data: true
testing:
  e2e: playwright
  unit: true
  integration: true
template_versions: {}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Slug — lowercase, letters/digits/hyphens |
| `family` | string | Template name from `boilerworks list` |
| `size` | `full` \| `micro` \| `edge` | Template size |
| `topology` | `standard` \| `omni` \| `api-only` | Project structure |
| `cloud` | `aws` \| `gcp` \| `azure` \| null | Cloud provider for infra |
| `ops` | bool | Include boilerworks-opscode |
| `region` | string | Cloud region |
| `domain` | string | App domain |
| `mobile` | bool | Include mobile template (Full only) |
| `web_presence` | bool | Include marketing site (Full only) |
| `compliance` | list | `soc2`, `hipaa`, `pci-dss`, `gdpr` |

## Topologies

**Standard** (default) — separate directories:
```
my-app/          ← app repo (git init'd)
my-app-ops/      ← Terraform repo (git init'd, if ops=true)
```

**Omni** — single repo:
```
my-app/
  ...app files...
  ops/             ← Terraform lives here
```

**API-only** — no frontend:
```
my-app/            ← backend only
```

## annotated example

See [`boilerworks.yaml.example`](https://github.com/ConflictHQ/boilerworks/blob/main/boilerworks.yaml.example) in the repo for a fully annotated manifest with all fields and their defaults.
