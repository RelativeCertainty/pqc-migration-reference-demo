interface CloudflareRequestMetadata {
  httpProtocol?: string;
  tlsCipher?: string;
  tlsVersion?: string;
}

export type RequestWithCloudflareMetadata = Request & {
  cf?: CloudflareRequestMetadata;
};

export const API_SECURITY_HEADERS = Object.freeze({
  "Cache-Control": "no-store",
  "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
  "Cross-Origin-Resource-Policy": "same-origin",
  "Permissions-Policy":
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()",
  "Referrer-Policy": "no-referrer",
  "Strict-Transport-Security": "max-age=31536000",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-Robots-Tag": "noindex, nofollow, noarchive",
});

export interface PosturePayload {
  schema_version: "pqc-posture.v2";
  evidence_tier: "request_transport_observation";
  observed_at: string;
  hostname: string;
  request_transport: {
    tls_version: { state: "observed" | "unavailable"; value: string | null };
    tls_cipher: { state: "observed" | "unavailable"; value: string | null };
    http_protocol: { state: "observed" | "unavailable"; value: string | null };
    exact_session_key_exchange: {
      state: "not_observable";
      explanation: string;
    };
  };
  hostname_capability: {
    state: "not_observable_by_handler";
    explanation: string;
  };
  visitor_edge_post_quantum_signatures: {
    state: "not_deployed";
    explanation: string;
  };
  access_control: {
    state: "not_observable_by_handler";
    target: "Cloudflare Access";
  };
  evidence_separation: {
    algorithm_standards: string;
    cryptographic_module: string;
  };
  data_posture: {
    storage: "none";
    upstream_origin_dependency: "none";
    dataset: "synthetic_only";
    request_logging: "not_implemented_by_application";
  };
  approved_deployment_label: {
    label: "PQC migration reference package";
    eligible: false;
    reason: string;
  };
}

function observed(value: string | undefined) {
  return value
    ? ({ state: "observed", value } as const)
    : ({ state: "unavailable", value: null } as const);
}

export function buildPosturePayload(request: RequestWithCloudflareMetadata): PosturePayload {
  const url = new URL(request.url);
  const cf = request.cf;

  return {
    schema_version: "pqc-posture.v2",
    evidence_tier: "request_transport_observation",
    observed_at: new Date().toISOString(),
    hostname: url.hostname,
    request_transport: {
      tls_version: observed(cf?.tlsVersion),
      tls_cipher: observed(cf?.tlsCipher),
      http_protocol: observed(cf?.httpProtocol),
      exact_session_key_exchange: {
        state: "not_observable",
        explanation:
          "Cloudflare request metadata exposes TLS version and cipher, but not the exact key exchange negotiated for this browser session.",
      },
    },
    hostname_capability: {
      state: "not_observable_by_handler",
      explanation:
        "Hybrid post-quantum TLS capability requires separate exact-host evidence. This request handler cannot observe or infer it from TLS version or cipher metadata.",
    },
    visitor_edge_post_quantum_signatures: {
      state: "not_deployed",
      explanation:
        "This reference deployment does not deploy or claim post-quantum signatures on the visitor-to-edge connection. Signatures and key agreement are separate properties.",
    },
    access_control: {
      state: "not_observable_by_handler",
      target: "Cloudflare Access",
    },
    evidence_separation: {
      algorithm_standards:
        "NIST algorithm publications are documentary evidence; they are not measured by this request endpoint.",
      cryptographic_module:
        "No FIPS 140 cryptographic-module validation evidence is asserted for this application or its edge runtime.",
    },
    data_posture: {
      storage: "none",
      upstream_origin_dependency: "none",
      dataset: "synthetic_only",
      request_logging: "not_implemented_by_application",
    },
    approved_deployment_label: {
      label: "PQC migration reference package",
      eligible: false,
      reason:
        "The request handler cannot promote this label. Exact-host capability, authenticated owner use, unrelated-identity denial, and reviewed deployment evidence remain separate gates.",
    },
  };
}
