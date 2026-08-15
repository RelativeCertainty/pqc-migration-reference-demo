package main

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func testApplication(t *testing.T) *application {
	t.Helper()
	fixedNow := time.Date(2026, time.August, 13, 18, 0, 0, 0, time.UTC)
	app, err := newApplication(testUI(), func() time.Time { return fixedNow })
	if err != nil {
		t.Fatalf("newApplication returned error: %v", err)
	}
	return app
}

func performRequest(app http.Handler, method, target, host string) *httptest.ResponseRecorder {
	request := httptest.NewRequest(method, target, nil)
	request.Host = host
	response := httptest.NewRecorder()
	app.ServeHTTP(response, request)
	return response
}

func TestPostureRouteIgnoresForwardingHeadersAndAppliesSecurityPolicy(t *testing.T) {
	app := testApplication(t)
	request := httptest.NewRequest(http.MethodGet, "http://portable.invalid/api/posture", nil)
	request.Host = "Demo.Example:8443"
	request.Header.Set("Forwarded", "host=forged.example;proto=https")
	request.Header.Set("X-Forwarded-Host", "forged.example")
	request.Header.Set("X-Forwarded-Proto", "https")
	response := httptest.NewRecorder()
	app.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	var payload posturePayload
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode posture response: %v", err)
	}
	if payload.Hostname != "demo.example" {
		t.Fatalf("hostname = %q, want normalized direct Host", payload.Hostname)
	}
	if payload.RequestTransport.TLSVersion.State != "unavailable" {
		t.Fatal("forwarding headers must not promote transport evidence")
	}
	for name, value := range commonSecurityHeaders {
		if got := response.Header().Get(name); got != value {
			t.Errorf("header %s = %q, want %q", name, got, value)
		}
	}
	if got := response.Header().Get("Content-Security-Policy"); got != apiCSP {
		t.Errorf("API CSP = %q, want %q", got, apiCSP)
	}
	if got := response.Header().Get("Cache-Control"); got != "no-store" {
		t.Errorf("Cache-Control = %q, want no-store", got)
	}
}

func TestReadOnlyAPIAndHealthRoutes(t *testing.T) {
	app := testApplication(t)
	tests := []struct {
		method string
		path   string
		status int
	}{
		{http.MethodHead, "/api/posture", http.StatusOK},
		{http.MethodPost, "/api/posture", http.StatusMethodNotAllowed},
		{http.MethodGet, "/api/unknown", http.StatusNotFound},
		{http.MethodGet, "/healthz", http.StatusOK},
		{http.MethodHead, "/readyz", http.StatusOK},
		{http.MethodPut, "/readyz", http.StatusMethodNotAllowed},
	}
	for _, test := range tests {
		t.Run(test.method+" "+test.path, func(t *testing.T) {
			response := performRequest(app, test.method, test.path, "demo.example")
			if response.Code != test.status {
				t.Fatalf("status = %d, want %d", response.Code, test.status)
			}
			if test.method == http.MethodHead && response.Body.Len() != 0 {
				t.Fatalf("HEAD body length = %d, want 0", response.Body.Len())
			}
		})
	}
}

func TestStaticAssetsAndSPAFallback(t *testing.T) {
	app := testApplication(t)
	tests := []struct {
		path        string
		status      int
		contentType string
		cache       string
		body        string
	}{
		{"/", http.StatusOK, "text/html; charset=utf-8", "no-store", `<div id="root"></div>`},
		{"/interview", http.StatusOK, "text/html; charset=utf-8", "no-store", `<div id="root"></div>`},
		{"/assets/index-ABC123.js", http.StatusOK, "text/javascript; charset=utf-8", "public, max-age=31536000, immutable", "synthetic demo"},
		{"/robots.txt", http.StatusOK, "text/plain; charset=utf-8", "no-store", "Disallow"},
		{"/assets/missing.js", http.StatusNotFound, "application/json; charset=utf-8", "no-store", "not_found"},
		{"/missing.txt", http.StatusNotFound, "application/json; charset=utf-8", "no-store", "not_found"},
		{"/_headers", http.StatusNotFound, "application/json; charset=utf-8", "no-store", "not_found"},
	}
	for _, test := range tests {
		t.Run(test.path, func(t *testing.T) {
			response := performRequest(app, http.MethodGet, "http://demo.example"+test.path, "demo.example")
			if response.Code != test.status {
				t.Fatalf("status = %d, want %d", response.Code, test.status)
			}
			if got := response.Header().Get("Content-Type"); got != test.contentType {
				t.Errorf("Content-Type = %q, want %q", got, test.contentType)
			}
			if got := response.Header().Get("Cache-Control"); got != test.cache {
				t.Errorf("Cache-Control = %q, want %q", got, test.cache)
			}
			if !strings.Contains(response.Body.String(), test.body) {
				t.Errorf("body does not contain %q", test.body)
			}
		})
	}
}

func TestRejectsMalformedHostAndUnsafePaths(t *testing.T) {
	app := testApplication(t)
	badHost := performRequest(app, http.MethodGet, "http://demo.example/", "forged.example:bad")
	if badHost.Code != http.StatusBadRequest {
		t.Fatalf("malformed Host status = %d, want 400", badHost.Code)
	}

	for _, target := range []string{
		"http://demo.example/assets/%2e%2e/index.html",
		"http://demo.example/.env",
		"http://demo.example/assets//index.js",
	} {
		response := performRequest(app, http.MethodGet, target, "demo.example")
		if response.Code != http.StatusNotFound {
			t.Errorf("unsafe target %q status = %d, want 404", target, response.Code)
		}
	}
}

func TestGracefulContextCancellation(t *testing.T) {
	app := testApplication(t)
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	server := &http.Server{
		Handler:           app,
		ReadHeaderTimeout: time.Second,
		ErrorLog:          log.New(io.Discard, "", 0),
	}
	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	go func() {
		result <- serveUntilCanceled(ctx, server, listener, time.Second)
	}()

	response, err := http.Get("http://" + listener.Addr().String() + "/readyz")
	if err != nil {
		cancel()
		t.Fatalf("readiness request: %v", err)
	}
	_ = response.Body.Close()
	if response.StatusCode != http.StatusOK {
		cancel()
		t.Fatalf("readiness status = %d, want 200", response.StatusCode)
	}
	cancel()
	select {
	case err := <-result:
		if err != nil {
			t.Fatalf("serveUntilCanceled returned error: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("server did not stop within the graceful-shutdown deadline")
	}
}

func TestNormalizeHostname(t *testing.T) {
	tests := map[string]string{
		"Demo.Example:8080": "demo.example",
		"localhost":         "localhost",
		"[::1]:8080":        "::1",
		"127.0.0.1:8080":    "127.0.0.1",
	}
	for input, want := range tests {
		got, err := normalizeHostname(input)
		if err != nil || got != want {
			t.Errorf("normalizeHostname(%q) = %q, %v; want %q, nil", input, got, err, want)
		}
	}
	for _, input := range []string{"", "bad host", "example.com:0", "::1", "-bad.example", "bad_.example"} {
		if _, err := normalizeHostname(input); err == nil {
			t.Errorf("normalizeHostname(%q) succeeded, want error", input)
		}
	}
}
