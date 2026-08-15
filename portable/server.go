package main

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"net"
	"net/http"
	"path"
	"strconv"
	"strings"
	"time"
)

const (
	apiCSP    = "default-src 'none'; frame-ancestors 'none'"
	staticCSP = "default-src 'self'; base-uri 'self'; connect-src 'self'; font-src 'self'; form-action 'none'; frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; script-src 'self'; style-src 'self'; upgrade-insecure-requests"
)

var commonSecurityHeaders = map[string]string{
	"Cross-Origin-Resource-Policy": "same-origin",
	"Permissions-Policy":           "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()",
	"Referrer-Policy":              "no-referrer",
	"Strict-Transport-Security":    "max-age=31536000",
	"X-Content-Type-Options":       "nosniff",
	"X-Frame-Options":              "DENY",
	"X-Robots-Tag":                 "noindex, nofollow, noarchive",
}

type application struct {
	assets *assetStore
	now    func() time.Time
}

func newApplication(ui fs.FS, now func() time.Time) (*application, error) {
	assets, err := loadAssetStore(ui)
	if err != nil {
		return nil, err
	}
	if now == nil {
		now = time.Now
	}
	return &application{assets: assets, now: now}, nil
}

func (app *application) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	hostname, err := normalizeHostname(request.Host)
	if err != nil {
		app.writeJSON(writer, request, http.StatusBadRequest, map[string]string{
			"error":   "bad_request",
			"message": "The request Host header is invalid.",
		}, false)
		return
	}
	if !safeRequestPath(request.URL.Path, request.URL.EscapedPath()) {
		app.writeJSON(writer, request, http.StatusNotFound, map[string]string{
			"error":   "not_found",
			"message": "Unknown route.",
		}, false)
		return
	}

	requestPath := request.URL.Path
	if strings.HasPrefix(requestPath, "/api/") {
		app.serveAPI(writer, request, hostname)
		return
	}
	if requestPath == "/healthz" || requestPath == "/readyz" {
		app.serveHealth(writer, request)
		return
	}
	if request.Method != http.MethodGet && request.Method != http.MethodHead {
		app.writeJSON(writer, request, http.StatusMethodNotAllowed, map[string]string{
			"error":   "method_not_allowed",
			"message": "This read-only application accepts GET and HEAD only.",
		}, true)
		return
	}
	app.serveStatic(writer, request)
}

func (app *application) serveAPI(writer http.ResponseWriter, request *http.Request, hostname string) {
	if request.Method != http.MethodGet && request.Method != http.MethodHead {
		app.writeJSON(writer, request, http.StatusMethodNotAllowed, map[string]string{
			"error":   "method_not_allowed",
			"message": "This read-only endpoint accepts GET and HEAD only.",
		}, true)
		return
	}
	if request.URL.Path == "/api/posture" {
		app.writeJSON(writer, request, http.StatusOK, buildPortablePosture(hostname, app.now()), true)
		return
	}
	app.writeJSON(writer, request, http.StatusNotFound, map[string]string{
		"error":   "not_found",
		"message": "Unknown API route.",
	}, true)
}

func (app *application) serveHealth(writer http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodGet && request.Method != http.MethodHead {
		app.writeJSON(writer, request, http.StatusMethodNotAllowed, map[string]string{
			"error":   "method_not_allowed",
			"message": "This read-only endpoint accepts GET and HEAD only.",
		}, true)
		return
	}
	app.writeJSON(writer, request, http.StatusOK, map[string]string{"status": "ok"}, true)
}

func (app *application) serveStatic(writer http.ResponseWriter, request *http.Request) {
	name := strings.TrimPrefix(request.URL.Path, "/")
	if name == "" {
		name = "index.html"
	}
	if name == "_headers" || name == assetManifestName {
		app.writeJSON(writer, request, http.StatusNotFound, map[string]string{
			"error":   "not_found",
			"message": "Unknown route.",
		}, false)
		return
	}

	if body, ok := app.assets.files[name]; ok {
		app.writeAsset(writer, request, name, body)
		return
	}
	if strings.HasPrefix(name, "assets/") || strings.Contains(path.Base(name), ".") {
		app.writeJSON(writer, request, http.StatusNotFound, map[string]string{
			"error":   "not_found",
			"message": "Unknown static asset.",
		}, false)
		return
	}
	app.writeAsset(writer, request, "index.html", app.assets.files["index.html"])
}

func (app *application) writeAsset(writer http.ResponseWriter, request *http.Request, name string, body []byte) {
	applyCommonHeaders(writer.Header())
	writer.Header().Set("Content-Security-Policy", staticCSP)
	writer.Header().Set("Cross-Origin-Opener-Policy", "same-origin")
	if strings.HasPrefix(name, "assets/") {
		writer.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
	} else {
		writer.Header().Set("Cache-Control", "no-store")
	}
	writer.Header().Set("Content-Type", stableContentType(name))
	writer.Header().Set("Content-Length", strconv.Itoa(len(body)))
	writer.WriteHeader(http.StatusOK)
	if request.Method != http.MethodHead {
		_, _ = writer.Write(body)
	}
}

func (app *application) writeJSON(
	writer http.ResponseWriter,
	request *http.Request,
	status int,
	payload any,
	allowReadOnly bool,
) {
	body, err := json.Marshal(payload)
	if err != nil {
		status = http.StatusInternalServerError
		body = []byte(`{"error":"internal_error","message":"Unable to encode response."}`)
	}
	applyCommonHeaders(writer.Header())
	writer.Header().Set("Cache-Control", "no-store")
	writer.Header().Set("Content-Security-Policy", apiCSP)
	writer.Header().Set("Content-Type", "application/json; charset=utf-8")
	if allowReadOnly {
		writer.Header().Set("Allow", "GET, HEAD")
	}
	writer.Header().Set("Content-Length", strconv.Itoa(len(body)))
	writer.WriteHeader(status)
	if request.Method != http.MethodHead {
		_, _ = writer.Write(body)
	}
}

func applyCommonHeaders(headers http.Header) {
	for name, value := range commonSecurityHeaders {
		headers.Set(name, value)
	}
}

func stableContentType(name string) string {
	switch strings.ToLower(path.Ext(name)) {
	case ".html":
		return "text/html; charset=utf-8"
	case ".js", ".mjs":
		return "text/javascript; charset=utf-8"
	case ".css":
		return "text/css; charset=utf-8"
	case ".json", ".map":
		return "application/json; charset=utf-8"
	case ".txt":
		return "text/plain; charset=utf-8"
	case ".svg":
		return "image/svg+xml"
	case ".png":
		return "image/png"
	case ".jpg", ".jpeg":
		return "image/jpeg"
	case ".webp":
		return "image/webp"
	case ".woff":
		return "font/woff"
	case ".woff2":
		return "font/woff2"
	default:
		return "application/octet-stream"
	}
}

func safeRequestPath(decoded, escaped string) bool {
	if decoded == "" || !strings.HasPrefix(decoded, "/") || strings.ContainsAny(decoded, "\\\x00\r\n") {
		return false
	}
	lowerEscaped := strings.ToLower(escaped)
	for _, forbidden := range []string{"%00", "%2e", "%2f", "%5c"} {
		if strings.Contains(lowerEscaped, forbidden) {
			return false
		}
	}
	segments := strings.Split(strings.TrimPrefix(decoded, "/"), "/")
	for index, segment := range segments {
		if segment == "." || segment == ".." || strings.HasPrefix(segment, ".") {
			return false
		}
		if segment == "" && index != len(segments)-1 {
			return false
		}
	}
	return true
}

func normalizeHostname(raw string) (string, error) {
	if raw == "" || len(raw) > 259 || strings.ContainsAny(raw, " /\\\t\r\n\x00") {
		return "", fmt.Errorf("invalid Host header")
	}

	host := raw
	if strings.HasPrefix(raw, "[") {
		closing := strings.IndexByte(raw, ']')
		if closing < 0 {
			return "", fmt.Errorf("invalid bracketed host")
		}
		host = raw[1:closing]
		remainder := raw[closing+1:]
		if remainder != "" {
			if !strings.HasPrefix(remainder, ":") || !validPort(strings.TrimPrefix(remainder, ":")) {
				return "", fmt.Errorf("invalid host port")
			}
		}
		if net.ParseIP(host) == nil {
			return "", fmt.Errorf("invalid IP host")
		}
		return strings.ToLower(host), nil
	}

	switch strings.Count(raw, ":") {
	case 0:
		host = raw
	case 1:
		var port string
		var err error
		host, port, err = net.SplitHostPort(raw)
		if err != nil || !validPort(port) {
			return "", fmt.Errorf("invalid host port")
		}
	default:
		return "", fmt.Errorf("unbracketed IPv6 host")
	}

	host = strings.TrimSuffix(strings.ToLower(host), ".")
	if host == "" || len(host) > 253 {
		return "", fmt.Errorf("invalid hostname length")
	}
	if net.ParseIP(host) != nil {
		return host, nil
	}
	for _, label := range strings.Split(host, ".") {
		if label == "" || len(label) > 63 || label[0] == '-' || label[len(label)-1] == '-' {
			return "", fmt.Errorf("invalid hostname label")
		}
		for _, character := range label {
			if (character < 'a' || character > 'z') && (character < '0' || character > '9') && character != '-' {
				return "", fmt.Errorf("invalid hostname character")
			}
		}
	}
	return host, nil
}

func validPort(raw string) bool {
	port, err := strconv.Atoi(raw)
	return err == nil && port >= 1 && port <= 65535
}
