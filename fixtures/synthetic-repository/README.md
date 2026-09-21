# Synthetic repository-scanner input

This directory is read-only scanner input, not an application dependency or an
installable service. Do not run npm install here. The package declaration and
source strings let the scanner demonstrate cryptographic-dependency discovery
without executing cryptographic code or making vulnerability claims.

The declared node-forge version is patched; the scanner should recognize the
software independently of whether that version has a known vulnerability.
Tests use the same example version. Application dependencies are acquired only
through the maintained frontend and C# lockfiles described in the root README.
