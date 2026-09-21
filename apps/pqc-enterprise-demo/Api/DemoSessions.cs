using System.Security.Cryptography;
using System.Text;

namespace PqcEnterpriseDemo.Api;

internal sealed record DemoSession(string Token, string Role, string PrincipalId, string DisplayName, string CsrfToken, DateTimeOffset ExpiresAt);

/// <summary>
/// Explicitly synthetic, process-local demonstration identity. No enterprise SSO,
/// real password, persisted credential, delegated authority, or public login.
/// Cookies cannot be Secure on this deliberately HTTP-loopback-only profile;
/// production HTTPS authentication is a separate, activation-blocked integration.
/// </summary>
internal sealed class DemoSessions(int port)
{
    internal static readonly IReadOnlyDictionary<string, string> Personas = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["analyst"] = "Assessment lead", ["contributor"] = "Source contributor",
        ["contributor-two"] = "Second source contributor",
        ["reviewer"] = "Technical review lead", ["sponsor"] = "Engagement sponsor",
        ["information-owner"] = "Information owner", ["risk-lead"] = "Risk lead",
        ["business-reviewer"] = "Business review lead", ["viewer"] = "Read-only viewer"
    };
    public const string ContextKey = "pqc.synthetic.session";
    private readonly object gate = new();
    private readonly Dictionary<string, DemoSession> sessions = new(StringComparer.Ordinal);
    private readonly Queue<DateTimeOffset> loginAttempts = new();
    private readonly Queue<DateTimeOffset> reportAttempts = new();
    private readonly Queue<DateTimeOffset> actionAttempts = new();
    private readonly string cookieName = $"pqc_synthetic_session_{port}";
    private static readonly TimeSpan Lifetime = TimeSpan.FromMinutes(30);

    public static DemoSession? Current(HttpContext context) => context.Items[ContextKey] as DemoSession;

    public static object View(DemoSession? session) => new
    {
        authenticated = session is not null,
        role = session?.Role,
        principalId = session?.PrincipalId,
        displayName = session?.DisplayName,
        synthetic = true,
        csrfToken = session?.CsrfToken,
        identityBoundary = "synthetic-local-demo-not-enterprise-sso"
    };

    public DemoSession? Find(HttpContext context)
    {
        var token = context.Request.Cookies[cookieName];
        if (token is null || token.Length != 64)
            return null;
        lock (gate)
        {
            Prune();
            return sessions.GetValueOrDefault(token);
        }
    }

    public DemoSession Create(HttpContext context, string role)
    {
        if (!Personas.TryGetValue(role, out var name)) throw new DemoHttpException(401, "invalid_demo_identity");
        var now = DateTimeOffset.UtcNow;
        var session = new DemoSession(RandomToken(), role, "synthetic-demo:" + role, name, RandomToken(), now.Add(Lifetime));
        lock (gate)
        {
            Prune();
            var previous = context.Request.Cookies[cookieName];
            if (previous is not null)
                sessions.Remove(previous);
            if (sessions.Count >= 64)
                throw new DemoHttpException(429, "session_limit_reached");
            sessions.Add(session.Token, session);
        }
        context.Response.Cookies.Append(cookieName, session.Token, new CookieOptions
        {
            HttpOnly = true,
            SameSite = SameSiteMode.Strict,
            Secure = false,
            IsEssential = true,
            Path = "/",
            MaxAge = Lifetime,
            Expires = session.ExpiresAt
        });
        return session;
    }

    public void Remove(HttpContext context)
    {
        var token = context.Request.Cookies[cookieName];
        lock (gate)
            if (token is not null)
                sessions.Remove(token);
        context.Response.Cookies.Delete(cookieName, new CookieOptions
        {
            HttpOnly = true,
            SameSite = SameSiteMode.Strict,
            Secure = false,
            Path = "/"
        });
    }

    public bool ValidCsrf(HttpContext context, DemoSession session)
    {
        var token = context.Request.Headers["X-PQC-CSRF"].ToString();
        return token.Length == 64 && CryptographicOperations.FixedTimeEquals(
            Encoding.ASCII.GetBytes(token), Encoding.ASCII.GetBytes(session.CsrfToken));
    }

    public void AdmitLogin() => Admit(loginAttempts, 12);
    public void AdmitReport() => Admit(reportAttempts, 30);
    public void AdmitAction() => Admit(actionAttempts, 30);

    private void Admit(Queue<DateTimeOffset> attempts, int maximum)
    {
        lock (gate)
        {
            var now = DateTimeOffset.UtcNow;
            while (attempts.TryPeek(out var oldest) && now - oldest >= TimeSpan.FromMinutes(1))
                attempts.Dequeue();
            if (attempts.Count >= maximum)
                throw new DemoHttpException(429, "rate_limit_reached");
            attempts.Enqueue(now);
        }
    }

    private void Prune()
    {
        var now = DateTimeOffset.UtcNow;
        foreach (var token in sessions.Where(pair => pair.Value.ExpiresAt <= now).Select(pair => pair.Key).ToArray())
            sessions.Remove(token);
    }

    private static string RandomToken() => Convert.ToHexString(RandomNumberGenerator.GetBytes(32)).ToLowerInvariant();
}
