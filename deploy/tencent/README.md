# Tencent Cloud server deployment

This branch is isolated from the `local` working branch. The app uses the existing DeepSeek and Semantic Scholar API configuration, stored only in `deploy/tencent/private/config.local.yaml` on the server. Neither that file nor `deploy/tencent/.env` is committed.

The Compose service binds only `127.0.0.1:18765` on the host. An existing Caddy or Nginx instance must terminate HTTPS for `clinkrag.hifuu.space` and proxy to this loopback port, rewriting `Host` to `127.0.0.1:8765`. See the examples in this folder. The app also requires HTTP Basic Auth; choose a long random password in `.env`. Its Basic Auth challenge is served through the HTTPS reverse proxy. Never expose port 18765 publicly.

Recommended server layout: clone this branch into `/opt/clinkrag`, create `deploy/tencent/private/config.local.yaml` and `deploy/tencent/.env` with mode 600, then run:

```sh
cd /opt/clinkrag/deploy/tencent
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Check the proxy and login before creating the Cloudflare DNS record for `clinkrag.hifuu.space`. For an Nginx host, add TLS using the host's existing certificate automation; the Nginx example shows only the upstream block. Persist `deploy/tencent/private/` and `deploy/tencent/data/` in server backups. The app has a single process because in-memory run supervision is not distributed.
