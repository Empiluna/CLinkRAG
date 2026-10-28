import { DurableObject } from 'cloudflare:workers';

const PORT = 8080;
const IDLE_MS = 12 * 60 * 60 * 1000;

export class ResearchContainer extends DurableObject {
  starting;

  async fetch(request) {
    this.starting ??= this.startAndWait().finally(() => { this.starting = undefined; });
    await this.starting;
    const url = new URL(request.url);
    url.protocol = 'http:';
    url.host = 'container';
    const forwarded = new Request(url, request);
    forwarded.headers.delete('host');
    forwarded.headers.delete('authorization');
    return this.ctx.container.getTcpPort(PORT).fetch(forwarded);
  }

  async startAndWait() {
    const container = this.ctx.container;
    if (!container.running) {
      const required = ['DEEPSEEK_API_KEY', 'S2_API_KEY', 'R2_ACCOUNT_ID',
        'R2_BUCKET_NAME', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'];
      if (required.some((key) => !this.env[key])) {
        throw new Error('Cloudflare secrets are incomplete');
      }
      container.start({
        image: container.images.base,
        instance: 'standard-2',
        enableInternet: true,
        env: {
          DEEPSEEK_API_KEY: this.env.DEEPSEEK_API_KEY,
          S2_API_KEY: this.env.S2_API_KEY,
          R2_ACCOUNT_ID: this.env.R2_ACCOUNT_ID,
          R2_BUCKET_NAME: this.env.R2_BUCKET_NAME,
          AWS_ACCESS_KEY_ID: this.env.AWS_ACCESS_KEY_ID,
          AWS_SECRET_ACCESS_KEY: this.env.AWS_SECRET_ACCESS_KEY,
        },
      });
    }
    await container.setInactivityTimeout(IDLE_MS);
    const port = container.getTcpPort(PORT);
    for (let attempt = 0; attempt < 120; attempt++) {
      try {
        const response = await port.fetch('http://container/health', {
          signal: AbortSignal.timeout(1000),
        });
        await response.body?.cancel();
        if (response.ok) return;
      } catch (_) { /* The image or model may still be starting. */ }
      await scheduler.wait(500);
    }
    throw new Error('Research container did not become ready');
  }
}

export default {
  fetch(request, env) {
    if (!env.APP_PASSWORD || env.APP_PASSWORD.length < 16) {
      return new Response('Service password is not configured', {status: 503});
    }
    const header = request.headers.get('authorization') || '';
    let user = '', password = '';
    if (header.startsWith('Basic ')) {
      try {
        const binary = atob(header.slice(6));
        const decoded = new TextDecoder().decode(Uint8Array.from(binary, (char) => char.charCodeAt(0)));
        const separator = decoded.indexOf(':');
        user = decoded.slice(0, separator);
        password = decoded.slice(separator + 1);
      } catch (_) { /* Invalid credentials. */ }
    }
    if (user !== 'admin' || password !== env.APP_PASSWORD) {
      return new Response('Authentication required', {
        status: 401,
        headers: {'WWW-Authenticate': 'Basic realm="CLinkRAG"', 'Cache-Control': 'no-store'},
      });
    }
    return env.RESEARCH_CONTAINER.getByName('primary').fetch(request);
  },
};
