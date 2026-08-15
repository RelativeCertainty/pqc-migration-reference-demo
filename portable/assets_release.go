//go:build portable_release

package main

import (
	"embed"
	"io/fs"
)

// generated-ui is produced only by scripts/stage-portable-assets.mjs from the
// exact Vite dist tree. The portable_release tag is required for release builds.
//
//go:embed all:generated-ui
var generatedUI embed.FS

func embeddedUI() (fs.FS, error) {
	return fs.Sub(generatedUI, "generated-ui")
}
