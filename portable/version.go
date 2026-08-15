package main

import (
	"encoding/json"
	"io"
	"runtime"
)

var (
	Version        = "0.0.0-development"
	GitSHA         = "unknown"
	SourceState    = "unknown"
	BuildTimestamp = "1970-01-01T00:00:00.000Z"
)

type versionPayload struct {
	Version          string `json:"version"`
	GitSHA           string `json:"git_sha"`
	SourceState      string `json:"source_state"`
	BuildTarget      string `json:"build_target"`
	BuildTimestamp   string `json:"build_timestamp"`
	UIManifestSHA256 string `json:"ui_manifest_sha256"`
}

func writeVersion(writer io.Writer, manifestDigest string) error {
	payload := versionPayload{
		Version:          Version,
		GitSHA:           GitSHA,
		SourceState:      SourceState,
		BuildTarget:      runtime.GOOS + "/" + runtime.GOARCH,
		BuildTimestamp:   BuildTimestamp,
		UIManifestSHA256: manifestDigest,
	}
	encoder := json.NewEncoder(writer)
	encoder.SetEscapeHTML(true)
	return encoder.Encode(payload)
}
