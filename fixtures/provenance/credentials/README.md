# Content Credentials demo fixtures

These are locally generated test images. The signer and root are for testing. The
root certificate is public and the private keys are excluded from these fixtures.

| State | File and validator setup | Expected result |
| --- | --- | --- |
| None | 01-no-credentials.png | Absent |
| Passing under the demo trust policy | 02-test-signed.png, with the demo anchor | Valid signature and binding, trusted by configured policy |
| Untrusted test-signed | 04-untrusted-test-signed.png, signed by a separate test root | Valid signature and binding, untrusted signer |
| Failing | 03-binding-fails-test-signed.png, with the demo anchor | Valid signature, failed binding, trusted signer under demo policy |

To show all four states in one analysis in Pratyaksh, start a separate local backend
with `PRATYAKSH_C2PA_DEMO_ANCHOR=fixtures/provenance/credentials/demo-trust-root.pem`
from the repository root. The report identifies the demo trust policy and
fingerprint. Use a fresh analysis after changing policy. The failing fixture
retains the manifest while replacing the PNG image-data chunk. The policy does
not change the cryptographic binding outcome.
