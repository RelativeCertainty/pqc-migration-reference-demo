package main

import (
	"strings"
	"testing"
	"testing/fstest"
)

func TestLoadAssetStoreVerifiesManifestAndTree(t *testing.T) {
	store, err := loadAssetStore(testUI())
	if err != nil {
		t.Fatalf("loadAssetStore returned error: %v", err)
	}
	if len(store.files) != 5 {
		t.Fatalf("loaded %d assets, want 5", len(store.files))
	}
	if len(store.manifestDigest) != 64 {
		t.Fatalf("manifest digest length = %d, want 64", len(store.manifestDigest))
	}
}

func TestLoadAssetStoreRejectsTamperingAndUnlistedFiles(t *testing.T) {
	tests := []struct {
		name string
		edit func(fstest.MapFS)
		want string
	}{
		{
			name: "tampered asset",
			edit: func(files fstest.MapFS) {
				files["index.html"] = &fstest.MapFile{Data: []byte("tampered"), Mode: 0o444}
			},
			want: "failed SHA-256 verification",
		},
		{
			name: "unlisted asset",
			edit: func(files fstest.MapFS) {
				files["extra.txt"] = &fstest.MapFile{Data: []byte("extra"), Mode: 0o444}
			},
			want: "tree contains",
		},
		{
			name: "source map",
			edit: func(files fstest.MapFS) {
				files[assetManifestName] = &fstest.MapFile{Data: []byte(strings.Repeat("0", 64) + "  bundle.js.map\n"), Mode: 0o444}
			},
			want: "unsafe asset path",
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			files := testUI()
			test.edit(files)
			_, err := loadAssetStore(files)
			if err == nil || !strings.Contains(err.Error(), test.want) {
				t.Fatalf("loadAssetStore error = %v, want substring %q", err, test.want)
			}
		})
	}
}

func TestSafeAssetNameRejectsTraversalAndHiddenContent(t *testing.T) {
	for _, name := range []string{"../index.html", ".env", "assets/.secret", "assets/app.js.map", "assets\\app.js"} {
		if safeAssetName(name) {
			t.Errorf("safeAssetName(%q) = true, want false", name)
		}
	}
}
