package main

import (
	"bytes"
	"encoding/json"
	"testing"
)

func TestWriteVersionContainsBoundedBuildIdentity(t *testing.T) {
	var output bytes.Buffer
	if err := writeVersion(&output, "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"); err != nil {
		t.Fatalf("writeVersion returned error: %v", err)
	}
	var payload versionPayload
	if err := json.Unmarshal(output.Bytes(), &payload); err != nil {
		t.Fatalf("decode version payload: %v", err)
	}
	if payload.BuildTarget == "" || payload.UIManifestSHA256 == "" {
		t.Fatalf("version payload is missing build target or UI digest: %#v", payload)
	}
	if payload.SourceState != "unknown" {
		t.Fatalf("default source state = %q, want unknown", payload.SourceState)
	}
}
