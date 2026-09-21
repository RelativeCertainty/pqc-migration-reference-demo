// SPDX-License-Identifier: MIT

import path from "node:path";
import process from "node:process";

import { CreateOnlyReportAdapter } from "./reports.ts";
import { createScanRepository } from "./scan.ts";
import {
  ContractError,
  InputBoundaryError,
  OutputBoundaryError,
  type ScanRequest,
} from "./types.ts";

class ArgumentError extends Error {
  readonly name = "ArgumentError";
}

interface ParsedArguments extends ScanRequest {
  outputDirectory: string;
}

function usage(): string {
  return [
    "usage: npm run scan:repo -- --root <authorized-directory> --label <safe-label> --out <new-directory>",
    "       [--exclude <relative-pattern>] [--synthetic] [--collected-at <UTC-timestamp>]",
  ].join("\n");
}

function parseArguments(arguments_: string[]): ParsedArguments {
  const values = new Map<string, string>();
  const excludes: string[] = [];
  let synthetic = false;

  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument === "--synthetic") {
      synthetic = true;
      continue;
    }
    if (!["--root", "--label", "--out", "--exclude", "--collected-at"].includes(argument)) {
      throw new ArgumentError("unknown or misplaced argument");
    }
    const value = arguments_[index + 1];
    if (value === undefined || value.startsWith("--")) throw new ArgumentError("argument value is missing");
    index += 1;
    if (argument === "--exclude") excludes.push(value);
    else if (values.has(argument)) throw new ArgumentError("argument was provided more than once");
    else values.set(argument, value);
  }

  const root = values.get("--root");
  const label = values.get("--label");
  const outputDirectory = values.get("--out");
  if (!root || !label || !outputDirectory) throw new ArgumentError("root, label, and out are required");

  const resolvedRoot = path.resolve(root);
  const resolvedOutput = path.resolve(outputDirectory);
  if (resolvedOutput === resolvedRoot || resolvedOutput.startsWith(`${resolvedRoot}${path.sep}`)) {
    throw new InputBoundaryError("output must be outside the selected root");
  }

  return {
    root: resolvedRoot,
    label,
    outputDirectory: resolvedOutput,
    excludes,
    synthetic,
    collectedAt: values.get("--collected-at"),
  };
}

async function main(): Promise<number> {
  let parsed: ParsedArguments;
  try {
    parsed = parseArguments(process.argv.slice(2));
  } catch (error) {
    if (error instanceof ArgumentError) {
      process.stderr.write(`${usage()}\ninvalid arguments: ${error.message}\n`);
      return 2;
    }
    if (error instanceof InputBoundaryError) {
      process.stderr.write("repository input boundary rejected\n");
      return 3;
    }
    return 5;
  }

  try {
    const result = await createScanRepository().execute(parsed);
    await new CreateOnlyReportAdapter().write(parsed.outputDirectory, result);
    process.stdout.write(
      `scan completed: ${result.summary.inspectedFiles} inspected, ${result.summary.observationCount} candidate observations, ${result.summary.warningCount} warnings\n`,
    );
    return 0;
  } catch (error) {
    if (error instanceof InputBoundaryError) {
      process.stderr.write("repository input boundary rejected\n");
      return 3;
    }
    if (error instanceof OutputBoundaryError) {
      process.stderr.write("create-only output boundary rejected\n");
      return 4;
    }
    if (error instanceof ContractError) {
      process.stderr.write("scanner contract or deterministic-processing boundary rejected\n");
      return 5;
    }
    process.stderr.write("scanner could not complete deterministically\n");
    return 5;
  }
}

process.exitCode = await main();
