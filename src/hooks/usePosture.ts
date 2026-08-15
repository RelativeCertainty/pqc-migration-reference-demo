import { useCallback, useEffect, useState } from "react";

import type { RuntimePosture } from "../domain/model";

type JsonObject = Record<string, unknown>;

function isClosedObject(value: unknown, keys: readonly string[]): value is JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function isBoundedText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maximum && /\S/u.test(value) && !/[\r\n\t]/u.test(value);
}

function isCanonicalTimestamp(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/u.test(value)) return false;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return false;
  return parsed.toISOString().slice(0, 19) === value.slice(0, 19);
}

function isObservation(value: unknown): boolean {
  if (!isClosedObject(value, ["state", "value"])) return false;
  return value.state === "unavailable"
    ? value.value === null
    : value.state === "observed" && isBoundedText(value.value, 128);
}

export function parseRuntimePosture(value: unknown): RuntimePosture {
  if (!isClosedObject(value, [
    "schema_version",
    "evidence_tier",
    "observed_at",
    "hostname",
    "request_transport",
    "hostname_capability",
    "visitor_edge_post_quantum_signatures",
    "access_control",
    "evidence_separation",
    "data_posture",
    "approved_deployment_label",
  ])) throw new Error("unexpected posture contract");

  if (value.schema_version !== "pqc-posture.v2" || value.evidence_tier !== "request_transport_observation") {
    throw new Error("unexpected posture contract");
  }
  if (!isCanonicalTimestamp(value.observed_at) || !isBoundedText(value.hostname, 253)) throw new Error("unexpected posture contract");

  if (!isClosedObject(value.request_transport, ["tls_version", "tls_cipher", "http_protocol", "exact_session_key_exchange"])) {
    throw new Error("unexpected posture contract");
  }
  const transport = value.request_transport;
  if (!isObservation(transport.tls_version) || !isObservation(transport.tls_cipher) || !isObservation(transport.http_protocol)) {
    throw new Error("unexpected posture contract");
  }
  if (!isClosedObject(transport.exact_session_key_exchange, ["state", "explanation"]) ||
      transport.exact_session_key_exchange.state !== "not_observable" ||
      !isBoundedText(transport.exact_session_key_exchange.explanation, 512)) throw new Error("unexpected posture contract");

  if (!isClosedObject(value.hostname_capability, ["state", "explanation"]) ||
      value.hostname_capability.state !== "not_observable_by_handler" ||
      !isBoundedText(value.hostname_capability.explanation, 512)) throw new Error("unexpected posture contract");
  if (!isClosedObject(value.visitor_edge_post_quantum_signatures, ["state", "explanation"]) ||
      value.visitor_edge_post_quantum_signatures.state !== "not_deployed" ||
      !isBoundedText(value.visitor_edge_post_quantum_signatures.explanation, 512)) throw new Error("unexpected posture contract");
  if (!isClosedObject(value.access_control, ["state", "target"]) ||
      value.access_control.state !== "not_observable_by_handler" || value.access_control.target !== "Cloudflare Access") {
    throw new Error("unexpected posture contract");
  }
  if (!isClosedObject(value.evidence_separation, ["algorithm_standards", "cryptographic_module"]) ||
      !isBoundedText(value.evidence_separation.algorithm_standards, 512) ||
      !isBoundedText(value.evidence_separation.cryptographic_module, 512)) throw new Error("unexpected posture contract");
  if (!isClosedObject(value.data_posture, ["storage", "upstream_origin_dependency", "dataset", "request_logging"]) ||
      value.data_posture.storage !== "none" || value.data_posture.upstream_origin_dependency !== "none" ||
      value.data_posture.dataset !== "synthetic_only" ||
      value.data_posture.request_logging !== "not_implemented_by_application") throw new Error("unexpected posture contract");
  if (!isClosedObject(value.approved_deployment_label, ["label", "eligible", "reason"]) ||
      value.approved_deployment_label.label !== "PQC migration reference package" ||
      value.approved_deployment_label.eligible !== false ||
      !isBoundedText(value.approved_deployment_label.reason, 512)) throw new Error("unexpected posture contract");

  return value as unknown as RuntimePosture;
}

type PostureState =
  | { state: "loading"; payload: null; message: string }
  | { state: "observed"; payload: RuntimePosture; message: string }
  | { state: "unavailable"; payload: null; message: string };

export type PostureResult = PostureState & { retry: () => void };

export function usePosture(): PostureResult {
  const [attempt, setAttempt] = useState(0);
  const [posture, setPosture] = useState<PostureState>({
    state: "loading",
    payload: null,
    message: "Reading bounded request metadata…",
  });

  useEffect(() => {
    const controller = new AbortController();

    const load = async () => {
      try {
        const response = await fetch("/api/posture", {
          method: "GET",
          headers: { Accept: "application/json" },
          cache: "no-store",
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`posture endpoint returned ${response.status}`);
        const payload = parseRuntimePosture(await response.json());
        setPosture({
          state: "observed",
          payload,
          message: "Request metadata observed at the application edge. No visitor identifier was collected.",
        });
      } catch (error) {
        if (controller.signal.aborted) return;
        const reason = error instanceof Error ? error.message : "request failed";
        setPosture({
          state: "unavailable",
          payload: null,
          message: `Runtime posture is unavailable in this context (${reason}). Deployment claims remain unvalidated.`,
        });
      }
    };

    void load();
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setPosture({
      state: "loading",
      payload: null,
      message: "Retrying bounded request metadata…",
    });
    setAttempt((current) => current + 1);
  }, []);

  return { ...posture, retry };
}
