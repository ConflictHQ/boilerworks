# boilerworks list

List all available templates.

```bash
boilerworks list
boilerworks list --size full
boilerworks list --language python
boilerworks list --size micro --language go
```

## Options

| Option | Values | Description |
|--------|--------|-------------|
| `--size` | `full`, `micro`, `edge` | Filter by template size |
| `--language` | `python`, `ruby`, `typescript`, `php`, `java`, `go`, `elixir`, `rust` | Filter by primary language |

## Output

Displays a Rich table with columns:

- **Name** — template family name (pass to `boilerworks setup`)
- **Size** — Full / Micro / Edge
- **Language** — primary backend language
- **Frontend** — frontend framework (if any)
- **Status** — `done` (●), `building` (◐), `planned` (○)
- **Description** — one-line summary

## Template status

| Status | Meaning |
|--------|---------|
| `done` | Production-ready, live-tested |
| `building` | In progress |
| `planned` | On the roadmap |
