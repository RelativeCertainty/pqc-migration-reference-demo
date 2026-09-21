using System.Globalization;

namespace PqcEnterpriseDemo;

/// <summary>The former Go posture handler, inside the authenticated C# host.</summary>
public static class ReferenceEndpoints
{
    public static void MapReferenceEndpoints(this WebApplication app)
    {
        app.MapMethods("/api/posture", ["GET", "HEAD"], (HttpContext context) =>
        {
            context.Response.Headers.Allow = "GET, HEAD";
            context.Response.Headers.ContentSecurityPolicy = "default-src 'none'; frame-ancestors 'none'";
            return Results.Json(new
            {
                schema_version = "pqc-posture.v3",
                evidence_tier = "request_transport_observation",
                observed_at = DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", CultureInfo.InvariantCulture),
                hostname = context.Request.Host.Host,
                request_transport = new
                {
                    tls_version = new { state = "unavailable", value = (string?)null },
                    tls_cipher = new { state = "unavailable", value = (string?)null },
                    http_protocol = new { state = "observed", value = context.Request.Protocol },
                    exact_session_key_exchange = new { state = "not_observable", explanation = "The loopback application does not terminate upstream TLS. Forwarded headers cannot establish negotiated key exchange." }
                },
                hostname_capability = new { state = "not_observable_by_handler", explanation = "Hybrid key exchange requires separate exact-host testing; source code is not a handshake observation." },
                visitor_edge_post_quantum_signatures = new { state = "not_deployed", explanation = "This application does not deploy post-quantum visitor-edge signatures. Authentication and key establishment are separate properties." },
                access_control = new { state = "synthetic_session_only", target = "C# assessment-scoped demo authorization" },
                evidence_separation = new { algorithm_standards = "Algorithm publications are documentary evidence, not measurements of this request.", cryptographic_module = "No FIPS 140 module validation is asserted." },
                data_posture = new { storage = "isolated_sqlite", upstream_origin_dependency = "none", dataset = "synthetic_only", request_logging = "not_implemented_by_application" },
                approved_deployment_label = new { label = "PQC migration reference package", eligible = false, reason = "Synthetic sessions and development tests do not establish enterprise identity, deployment approval or owner acceptance." }
            });
        });
    }
}
