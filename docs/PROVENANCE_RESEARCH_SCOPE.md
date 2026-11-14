# Provenance and source attribution scope

| Question | How Pratyaksh handles it |
| --- | --- |
| Who supplied the case file and under what collection reference? | Intake records optional reported supplier, collection reference and receipt note. The case records the time and self-declared analyst. The provenance record carries this context into PDF and JSON. |
| Are two files byte-identical? | Compare SHA-256 of the preserved originals. |
| Do files share visual content? | Compare image regions or sampled video frames, and record geometric match evidence and scope. |
| What does the file say about its source? | Display recorded metadata and Content Credentials, including separate signature, file binding and signer trust results. |
| Which model generated the manipulation? | Requires a separately validated generator attribution method and a way to handle unknown generators. Current detector scores cover synthetic-media detection. |
| Which physical device captured it? | Requires separately validated device identification evidence. File metadata can record a camera make or model. |
| Which person appears in it? | Face identity verification is a separate biometric task. The current face-forgery signals concern manipulation. |

The pi-labs research list identifies separate work on model attribution, video device identification and face recognition. Its blockchain paper describes a dApp development platform. Pratyaksh's case handover uses an offline verifier and a separately retained SHA-256 manifest fingerprint. See [pi-labs research](https://www.pi-labs.ai/research/), [face-manipulated video attribution](https://doi.org/10.1109/MAPR67746.2025.11134019), [face embeddings](https://doi.org/10.1109/AVSS65446.2025.11149778), and [dApp development](https://doi.org/10.1109/BRAINS63024.2024.10732862).

For the demo, upload a file with a fictional supplier and collection reference. Open the comparison from the case and show the recorded receipt alongside the file hash and the evidence behind a graph link. Export the report and verify the handover package offline. The [screenshot benchmark](PROVENANCE_BENCHMARK_V1.md) records how repeated interface elements can create false visual links and how selecting the photo area changes the result.
