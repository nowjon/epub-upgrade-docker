# EPUB upgrade watcher (Docker)

[![Build and publish Docker image](https://github.com/nowjon/epub-upgrade-docker/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/nowjon/epub-upgrade-docker/actions/workflows/docker-publish.yml)

Source repository: **https://github.com/nowjon/epub-upgrade-docker**

Watches a directory tree for `.epub` files, detects **EPUB 2** from the OPF version inside the ZIP, and upgrades to **EPUB 3** in place using Calibre `ebook-convert`.

## Image (GitHub Actions)

After each push to the default branch, CI builds and pushes to **GitHub Container Registry**:

`ghcr.io/nowjon/epub-upgrade-docker:latest`

Pull:

```bash
docker pull ghcr.io/nowjon/epub-upgrade-docker:latest
```

If the package is private, log in first (use a GitHub personal access token with `read:packages`):

```bash
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u nowjon --password-stdin
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
  ghcr.io/nowjon/epub-upgrade-docker:latest
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

See `docker-compose.yml` for a template. To use the published image instead of a local build, set:

`image: ghcr.io/nowjon/epub-upgrade-docker:latest`

and remove or comment out the `build:` section.

## Note

Calibre conversion may normalize HTML/CSS. Keep backups if you need bit-identical files.
