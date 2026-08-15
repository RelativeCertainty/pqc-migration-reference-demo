import headersSource from "../../public/_headers?raw";
import packageSource from "../../package.json?raw";
import stylesSource from "../styles.css?raw";
import viteSource from "../../vite.config.ts?raw";
import wranglerSource from "../../wrangler.jsonc?raw";

describe("deployment security configuration", () => {
  it("disables public workers.dev and preview URLs and limits Worker-first routing", () => {
    const config = JSON.parse(wranglerSource) as {
      workers_dev: boolean;
      preview_urls: boolean;
      route?: unknown;
      routes?: unknown;
      account_id?: unknown;
      assets: {
        directory: string;
        binding: string;
        not_found_handling: string;
        run_worker_first: string[];
      };
    };
    expect(config.workers_dev).toBe(false);
    expect(config.preview_urls).toBe(false);
    expect(config.route).toBeUndefined();
    expect(config.routes).toBeUndefined();
    expect(config.account_id).toBeUndefined();
    expect(config.assets).toEqual({
      directory: "./dist",
      binding: "ASSETS",
      not_found_handling: "single-page-application",
      run_worker_first: ["/api/*", "/assets/*"],
    });
  });

  it("secures static assets without inline script or style allowances", () => {
    expect(headersSource).toContain("Content-Security-Policy:");
    expect(headersSource).toMatch(/\/\*\s+Cache-Control: no-store/);
    expect(headersSource).toMatch(
      /\/assets\/\*\s+! Cache-Control\s+Cache-Control: public, max-age=31536000, immutable/,
    );
    expect(headersSource).toContain("default-src 'self'");
    expect(headersSource).toContain("frame-ancestors 'none'");
    expect(headersSource).toContain("Strict-Transport-Security: max-age=31536000");
    expect(headersSource).toContain("X-Content-Type-Options: nosniff");
    expect(headersSource).toContain("X-Frame-Options: DENY");
    expect(headersSource).toContain("X-Robots-Tag: noindex, nofollow, noarchive");
    expect(headersSource).not.toContain("'unsafe-inline'");
    expect(headersSource).not.toContain("Access-Control-Allow-Origin");
  });

  it("does not ship production source maps and pins every dependency", () => {
    expect(viteSource).toContain("sourcemap: false");
    const packageJson = JSON.parse(packageSource) as {
      dependencies: Record<string, string>;
      devDependencies: Record<string, string>;
    };
    for (const version of Object.values({ ...packageJson.dependencies, ...packageJson.devDependencies })) {
      expect(version).toMatch(/^\d+\.\d+\.\d+(?:[-+].+)?$/);
    }
  });

  it("allows the evidence-fusion grid to shrink inside phone viewports", () => {
    expect(stylesSource).toMatch(
      /\.fusion-workbench\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
    expect(stylesSource).toMatch(
      /\.fusion-workbench \.block-heading\s*\{[^}]*flex-direction:\s*column/,
    );
    expect(stylesSource).toMatch(
      /\.fusion-workbench \.development-label\s*\{[^}]*white-space:\s*normal/,
    );
  });
});
