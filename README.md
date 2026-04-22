# EPUB upgrade watcher (Docker)

Watches a directory tree for `.epub` files, detects **EPUB 2** from the OPF version inside the ZIP, and upgrades to **EPUB 3** in place using Calibre `ebook-convert`.

## Image (GitHub Actions)

After each push to the default branch, CI builds and pushes to **GitHub Container Registry**:

`ghcr.io/<your-github-user-or-org>/<repo-name>:latest`

Pull (use your real path; names are lowercase):

```bash
docker pull ghcr.io/OWNER/REPO:latest
```

If the package is private, log in first:

```bash
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

## Run

```bash
docker run -d \
  --name epub-upgrade-watcher \
  --restart unless-stopped \
  -e WATCH_PATH=/data \
  -e CONVERT_EXISTING=false \
  -e USE_POLLING=true \
  -v /mnt/user/Media/Audiobooks:/data \
  ghcr.io/OWNER/REPO:latest
```

Set `CONVERT_EXISTING=true` once to scan the whole tree for EPUB 2 files at startup.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WATCH_PATH` | `/data` | Root to watch |
| `CONVERT_EXISTING` | `false` | Full recursive scan on startup |
| `USE_POLLING` | `true` | Use polling (better on NAS / mergerfs) |
| `POLL_INTERVAL_SECONDS` | `10` | Polling interval |
| `EVENT_DEBOUNCE_SECONDS` | `2` | Debounce after file events |
| `FILE_STABLE_SECONDS` | `5` | Wait for file size to stabilize |

## Compose

See `docker-compose.yml` for a template (adjust the image to `ghcr.io/OWNER/REPO:latest` if you use the registry image).

## Note

Calibre conversion may normalize HTML/CSS. Keep backups if you need bit-identical files.
