import {
  API_SECURITY_HEADERS,
  buildPosturePayload,
  type RequestWithCloudflareMetadata,
} from "./posture";

function jsonResponse(body: unknown, status = 200, headOnly = false): Response {
  const headers = new Headers(API_SECURITY_HEADERS);
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Allow", "GET, HEAD");

  return new Response(headOnly ? null : JSON.stringify(body), { status, headers });
}

function addAssetSecurityHeaders(response: Response): Response {
  const secured = new Response(response.body, response);
  for (const [name, value] of Object.entries(API_SECURITY_HEADERS)) {
    if (name !== "Cache-Control") {
      secured.headers.set(name, value);
    }
  }
  return secured;
}

const worker = {
  async fetch(request: RequestWithCloudflareMetadata, env: CloudflareBindings): Promise<Response> {
    const url = new URL(request.url);
    const headOnly = request.method === "HEAD";

    if (url.pathname.startsWith("/api/") && request.method !== "GET" && !headOnly) {
      return jsonResponse(
        { error: "method_not_allowed", message: "This read-only endpoint accepts GET and HEAD only." },
        405,
      );
    }

    if (url.pathname === "/api/posture") {
      return jsonResponse(buildPosturePayload(request), 200, headOnly);
    }

    if (url.pathname.startsWith("/api/")) {
      return jsonResponse({ error: "not_found", message: "Unknown API route." }, 404, headOnly);
    }

    const assetResponse = await env.ASSETS.fetch(request);
    if (
      url.pathname.startsWith("/assets/") &&
      assetResponse.headers.get("Content-Type")?.toLowerCase().includes("text/html")
    ) {
      return jsonResponse({ error: "not_found", message: "Unknown static asset." }, 404, headOnly);
    }

    return addAssetSecurityHeaders(assetResponse);
  },
} satisfies ExportedHandler<CloudflareBindings>;

export default worker;
