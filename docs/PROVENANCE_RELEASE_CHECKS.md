# Provenance local prototype — release checks

Validated on 12 November 2026. Scope: local image provenance and evidence handover for the hackathon demonstration.

## Automated checks

- 18 provenance tests passed, including geometric crop and controlled added-region difference tests, HEIC preservation, duplicate grouping, immutable reviews, saved-analysis extensions, corrupted chains, PDF integrity gates, exported hash fidelity and offline package tampering.
- 58 frontend tests passed.
- 10 existing case API tests passed; Aadya's case activity implementation was not modified.
- Production TypeScript/Vite build passed. Vite retains non-blocking dependency annotation and large-bundle warnings.

## Browser walkthrough

An isolated headless Chrome session exercised the live Vite/FastAPI application using the private seven-file phone-photo demonstration:

1. Uploaded the first five files, including native HEIC; preserved originals and readable previews returned.
2. Confirmed exact-copy grouping and opened geometric relation evidence and an aligned difference overlay.
3. Extended the saved analysis with two controls: seven files, 21 compared pairs, one exact-copy group, nine supported geometric relations, and two files without visual links.
4. Saved a reviewer interpretation in a new snapshot and reopened it after a page reload.
5. Filtered the graph by evidence type and selected source files by clicking graph nodes.
6. Read provenance activity and verified the supplied phone original against its preserved SHA-256.
7. Downloaded the evidence package; independently verified its manifest using the retained hash, all artifact hashes, seven originals, canonical report hash and event chain.
8. Checked that every preview loaded and that desktop (1440px) and mobile (390px) layouts had no horizontal overflow, including the handover hash instructions.
9. Rendered the PDF for visual review, including connection evidence, source metadata, credentials, reviewer notes, activity, limitations and the unsigned examiner block.

The private demonstration files and generated handover package remain in the ignored `Pratyaksh-Phone-Provenance-Demo` directory. No private phone images or metadata are used as public landing-page assets.

## Interpretation boundary

These are functional checks, not a statistical provenance accuracy benchmark. A matching region supports a possible relationship; it does not establish capture order, camera ownership, original uploader, forwarding history or face authenticity. Model benchmark metrics remain separate. This local release has self-declared analysts and unsigned reports; agency deployment requires additional identity, storage and external anchoring controls.
