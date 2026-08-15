package main

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestPortablePostureFailsClosed(t *testing.T) {
	observedAt := time.Date(2026, time.August, 13, 12, 0, 0, 0, time.FixedZone("test", -6*60*60))
	payload := buildPortablePosture("demo.example", observedAt)
	if payload.SchemaVersion != "pqc-posture.v2" || payload.EvidenceTier != "request_transport_observation" {
		t.Fatalf("posture contract = %q / %q, want v2 request observation", payload.SchemaVersion, payload.EvidenceTier)
	}

	if payload.ObservedAt != "2026-08-13T18:00:00Z" {
		t.Fatalf("ObservedAt = %q, want normalized UTC", payload.ObservedAt)
	}
	if payload.RequestTransport.TLSVersion.State != "unavailable" || payload.RequestTransport.TLSVersion.Value != nil {
		t.Fatalf("TLS version = %#v, want unavailable/null", payload.RequestTransport.TLSVersion)
	}
	if payload.RequestTransport.TLSCipher.State != "unavailable" || payload.RequestTransport.HTTPProtocol.State != "unavailable" {
		t.Fatal("portable transport evidence must remain unavailable")
	}
	if payload.RequestTransport.ExactSessionKeyExchange.State != "not_observable" {
		t.Fatal("exact session key exchange must remain not_observable")
	}
	if payload.HostnameCapability.State != "not_observable_by_handler" || payload.AccessControl.State != "not_observable_by_handler" {
		t.Fatal("request handler must not infer hostname capability or external access state")
	}
	if payload.ApprovedDeploymentLabel.Eligible {
		t.Fatal("request observation must not be eligible for the approved deployment label")
	}

	serialized, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal posture payload: %v", err)
	}
	lower := strings.ToLower(string(serialized))
	for _, forbidden := range []string{"ip_address", "client_ip", "cookie", "email", "user_agent", "authorization"} {
		if strings.Contains(lower, forbidden) {
			t.Errorf("posture payload contains forbidden visitor field %q", forbidden)
		}
	}
}
