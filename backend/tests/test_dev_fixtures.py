import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "backend" / "contracts"
FIXTURES = ROOT / "fixtures" / "dev"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(schema_name: str, payload: dict):
    schema = load(CONTRACTS / schema_name)
    registry = {
        load(CONTRACTS / "dashboard-finding-1.1.schema.json")["$id"]: load(CONTRACTS / "dashboard-finding-1.1.schema.json")
    }
    jsonschema.validate(payload, schema, resolver=jsonschema.RefResolver.from_schema(schema, store=registry), format_checker=jsonschema.FormatChecker())


def test_catalogue_and_all_fixture_records_are_strictly_valid():
    catalogue = load(FIXTURES / "case-evidence.json")
    assert catalogue["fixture_notice"]["marker"] == "__PRATYAKSH_FIXTURE_PAYLOAD__"
    validate("dashboard-case-evidence-1.1.schema.json", catalogue["data"])
    for evidence in catalogue["data"]["evidence"]:
        assert len(evidence["sha256"]) == 64
        assert evidence["hash_source"] == "client_declared"
        assert evidence["preserved"] is False
        assert evidence["fixture"] is True
    for path in sorted((FIXTURES / "runs").glob("RUN-*.json")):
        wrapper = load(path)
        assert wrapper["fixture_notice"]["marker"] == "__PRATYAKSH_FIXTURE_PAYLOAD__"
        validate("dashboard-run-1.1.schema.json", wrapper["data"])
    for path in sorted((FIXTURES / "evaluation").glob("*.json")):
        validate("dashboard-evaluation-1.1.schema.json", load(path)["data"])


def test_fixture_coverage_and_arithmetic():
    runs = [load(path)["data"] for path in sorted((FIXTURES / "runs").glob("RUN-*.json"))]
    findings = [finding for run in runs for finding in run["findings"]]
    assert {run["execution_status"] for run in runs} == {"completed", "partial", "queued", "running", "failed", "unsupported", "cancelled"}
    by_id = {run["run_id"]: run for run in runs}
    assert by_id["RUN-00ab"]["retry_of"] == "RUN-00aa"
    assert by_id["RUN-00ab"]["attempt"] == 2
    assert by_id["RUN-00ae"]["retry_of"] == "RUN-00ad"
    assert by_id["RUN-00ae"]["execution_status"] == "running"
    assert any(run["execution_status"] == "failed" and run["errors"][-1]["retryable"] is False for run in runs if run["errors"])
    assert {finding["execution_status"] for finding in findings} == {"completed", "queued", "running", "failed", "unsupported", "not_applicable", "cancelled"}
    assert {finding["result"] for finding in findings} >= {"indicators_detected", "no_indicators_detected", "inconclusive", None}
    assert {finding["error"]["retryable"] for finding in findings if finding["error"]} == {True, False}
    for run in runs:
        if run["coverage"]:
            coverage = run["coverage"]
            assert coverage["planned"] == coverage["examined"] + coverage["rejected"] + coverage["unexamined"]
    for path in (FIXTURES / "evaluation").glob("*.json"):
        item = load(path)["data"]
        if item["confusion_matrix"]:
            assert sum(item["confusion_matrix"].values()) == item["examined_count"]


def test_production_contracts_remain_version_1_0():
    assert load(CONTRACTS / "d1-finding.schema.json")["properties"]["schema_version"]["const"] == "1.0"
    assert load(CONTRACTS / "d1-run.schema.json")["properties"]["schema_version"]["const"] == "1.0"
