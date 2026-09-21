<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Evidence status

| Label | Meaning | What it does not prove |
| --- | --- | --- |
| concept | Architecture or method is described. | Executability or target behavior. |
| synthetic | Executable behavior uses fictional inputs. | Authorized target access or live behavior. |
| contract-tested | Versioned boundaries and expected behavior are checked. | A deployed change or enterprise coverage. |
| live-readback | An authorized target change is independently observed. | Sustained outcome or complete migration. |
| closed-loop | Change, readback, measurement, and rollback evidence are accepted. | Unbounded future correctness or certification. |

The checked-in browser records and repository fixture are synthetic. The
scanner contracts and tests are designed for contract-tested evidence, but a
release claim should identify the exact command and result used. No artifact
in this initial public candidate represents live-readback or closed-loop
evidence.
