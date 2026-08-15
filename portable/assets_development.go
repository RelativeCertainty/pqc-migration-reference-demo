//go:build !portable_release

package main

import (
	"fmt"
	"io/fs"
)

func embeddedUI() (fs.FS, error) {
	return nil, fmt.Errorf("portable UI assets are not embedded; run `npm run portable:build`")
}
