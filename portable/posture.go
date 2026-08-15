package main

import "time"

type observation struct {
	State string  `json:"state"`
	Value *string `json:"value"`
}

type posturePayload struct {
	SchemaVersion    string `json:"schema_version"`
	EvidenceTier     string `json:"evidence_tier"`
	ObservedAt       string `json:"observed_at"`
	Hostname         string `json:"hostname"`
	RequestTransport struct {
		TLSVersion              observation `json:"tls_version"`
		TLSCipher               observation `json:"tls_cipher"`
		HTTPProtocol            observation `json:"http_protocol"`
		ExactSessionKeyExchange struct {
			State       string `json:"state"`
			Explanation string `json:"explanation"`
		} `json:"exact_session_key_exchange"`
	} `json:"request_transport"`
	HostnameCapability struct {
		State       string `json:"state"`
		Explanation string `json:"explanation"`
	} `json:"hostname_capability"`
	VisitorEdgePostQuantumSignatures struct {
		State       string `json:"state"`
		Explanation string `json:"explanation"`
	} `json:"visitor_edge_post_quantum_signatures"`
	AccessControl struct {
		State  string `json:"state"`
		Target string `json:"target"`
	} `json:"access_control"`
	EvidenceSeparation struct {
		AlgorithmStandards  string `json:"algorithm_standards"`
		CryptographicModule string `json:"cryptographic_module"`
	} `json:"evidence_separation"`
	DataPosture struct {
		Storage                  string `json:"storage"`
		UpstreamOriginDependency string `json:"upstream_origin_dependency"`
		Dataset                  string `json:"dataset"`
		RequestLogging           string `json:"request_logging"`
	} `json:"data_posture"`
	ApprovedDeploymentLabel struct {
		Label    string `json:"label"`
		Eligible bool   `json:"eligible"`
		Reason   string `json:"reason"`
	} `json:"approved_deployment_label"`
}

func buildPortablePosture(hostname string, observedAt time.Time) posturePayload {
	payload := posturePayload{
		SchemaVersion: "pqc-posture.v2",
		EvidenceTier:  "request_transport_observation",
		ObservedAt:    observedAt.UTC().Format(time.RFC3339Nano),
		Hostname:      hostname,
	}
	payload.RequestTransport.TLSVersion = observation{State: "unavailable", Value: nil}
	payload.RequestTransport.TLSCipher = observation{State: "unavailable", Value: nil}
	payload.RequestTransport.HTTPProtocol = observation{State: "unavailable", Value: nil}
	payload.RequestTransport.ExactSessionKeyExchange.State = "not_observable"
	payload.RequestTransport.ExactSessionKeyExchange.Explanation =
		"The portable application does not terminate or inspect upstream TLS and cannot observe the exact key exchange for this browser session."
	payload.HostnameCapability.State = "not_observable_by_handler"
	payload.HostnameCapability.Explanation =
		"Hybrid post-quantum TLS capability requires separate exact-host evidence. This portable process cannot observe or infer it from proxy headers."
	payload.VisitorEdgePostQuantumSignatures.State = "not_deployed"
	payload.VisitorEdgePostQuantumSignatures.Explanation =
		"This reference deployment does not deploy or claim post-quantum signatures on the visitor-to-edge connection. Signatures and key agreement are separate properties."
	payload.AccessControl.State = "not_observable_by_handler"
	payload.AccessControl.Target = "Cloudflare Access"
	payload.EvidenceSeparation.AlgorithmStandards =
		"NIST algorithm publications are documentary evidence; they are not measured by this request endpoint."
	payload.EvidenceSeparation.CryptographicModule =
		"No FIPS 140 cryptographic-module validation evidence is asserted for this application or its runtime."
	payload.DataPosture.Storage = "none"
	payload.DataPosture.UpstreamOriginDependency = "none"
	payload.DataPosture.Dataset = "synthetic_only"
	payload.DataPosture.RequestLogging = "not_implemented_by_application"
	payload.ApprovedDeploymentLabel.Label = "PQC migration reference package"
	payload.ApprovedDeploymentLabel.Eligible = false
	payload.ApprovedDeploymentLabel.Reason =
		"The request handler cannot promote this label. Exact-host capability, authenticated owner use, unrelated-identity denial, and reviewed deployment evidence remain separate gates."
	return payload
}
