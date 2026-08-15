package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"testing/fstest"
)

func testUI() fstest.MapFS {
	files := map[string]string{
		"index.html":              `<!doctype html><div id="root"></div>`,
		"robots.txt":              "User-agent: *\nDisallow: /\n",
		"assets/index-ABC123.js":  "console.log('synthetic demo');\n",
		"assets/index-ABC123.css": "body { color: #fff; }\n",
		"_headers":                "/*\n  Cache-Control: no-store\n",
	}
	manifest := ""
	ordered := []string{
		"_headers",
		"assets/index-ABC123.css",
		"assets/index-ABC123.js",
		"index.html",
		"robots.txt",
	}
	result := make(fstest.MapFS, len(files)+1)
	for _, name := range ordered {
		body := []byte(files[name])
		digest := sha256.Sum256(body)
		manifest += fmt.Sprintf("%s  %s\n", hex.EncodeToString(digest[:]), name)
		result[name] = &fstest.MapFile{Data: body, Mode: 0o444}
	}
	result[assetManifestName] = &fstest.MapFile{Data: []byte(manifest), Mode: 0o444}
	return result
}
