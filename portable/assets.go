package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io/fs"
	"path"
	"sort"
	"strings"
)

const assetManifestName = "asset-manifest.sha256"

type assetStore struct {
	files          map[string][]byte
	manifestDigest string
}

func loadAssetStore(root fs.FS) (*assetStore, error) {
	manifest, err := fs.ReadFile(root, assetManifestName)
	if err != nil {
		return nil, fmt.Errorf("read embedded UI manifest: %w", err)
	}

	expected, err := parseAssetManifest(string(manifest))
	if err != nil {
		return nil, err
	}
	files := make(map[string][]byte, len(expected))

	for name, expectedDigest := range expected {
		body, readErr := fs.ReadFile(root, name)
		if readErr != nil {
			return nil, fmt.Errorf("read embedded UI asset %q: %w", name, readErr)
		}
		actualDigest := sha256.Sum256(body)
		if hex.EncodeToString(actualDigest[:]) != expectedDigest {
			return nil, fmt.Errorf("embedded UI asset %q failed SHA-256 verification", name)
		}
		files[name] = body
	}

	var discovered []string
	err = fs.WalkDir(root, ".", func(name string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() || name == assetManifestName {
			return nil
		}
		if entry.Type()&fs.ModeSymlink != 0 || !entry.Type().IsRegular() {
			return fmt.Errorf("embedded UI contains unsupported file type at %q", name)
		}
		discovered = append(discovered, name)
		return nil
	})
	if err != nil {
		return nil, fmt.Errorf("walk embedded UI assets: %w", err)
	}
	sort.Strings(discovered)
	if len(discovered) != len(expected) {
		return nil, fmt.Errorf("embedded UI manifest covers %d files but tree contains %d", len(expected), len(discovered))
	}
	for _, name := range discovered {
		if _, ok := expected[name]; !ok {
			return nil, fmt.Errorf("embedded UI file %q is absent from the SHA-256 manifest", name)
		}
	}
	if _, ok := files["index.html"]; !ok {
		return nil, fmt.Errorf("embedded UI manifest does not contain index.html")
	}

	manifestDigest := sha256.Sum256(manifest)
	return &assetStore{
		files:          files,
		manifestDigest: hex.EncodeToString(manifestDigest[:]),
	}, nil
}

func parseAssetManifest(raw string) (map[string]string, error) {
	expected := make(map[string]string)
	scanner := bufio.NewScanner(strings.NewReader(raw))
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		line := scanner.Text()
		if line == "" {
			return nil, fmt.Errorf("embedded UI manifest contains an empty line at %d", lineNumber)
		}
		parts := strings.SplitN(line, "  ", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("embedded UI manifest line %d is malformed", lineNumber)
		}
		digest, name := parts[0], parts[1]
		if len(digest) != sha256.Size*2 || strings.ToLower(digest) != digest {
			return nil, fmt.Errorf("embedded UI manifest line %d has an invalid SHA-256 digest", lineNumber)
		}
		if _, err := hex.DecodeString(digest); err != nil {
			return nil, fmt.Errorf("embedded UI manifest line %d has an invalid SHA-256 digest", lineNumber)
		}
		if !safeAssetName(name) || name == assetManifestName {
			return nil, fmt.Errorf("embedded UI manifest line %d has an unsafe asset path", lineNumber)
		}
		if _, duplicate := expected[name]; duplicate {
			return nil, fmt.Errorf("embedded UI manifest contains duplicate asset %q", name)
		}
		expected[name] = digest
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("scan embedded UI manifest: %w", err)
	}
	if len(expected) == 0 {
		return nil, fmt.Errorf("embedded UI manifest is empty")
	}
	return expected, nil
}

func safeAssetName(name string) bool {
	if !fs.ValidPath(name) || path.IsAbs(name) || strings.Contains(name, "\\") {
		return false
	}
	for _, segment := range strings.Split(name, "/") {
		if segment == "" || segment == "." || segment == ".." || strings.HasPrefix(segment, ".") {
			return false
		}
	}
	return !strings.HasSuffix(strings.ToLower(name), ".map")
}
