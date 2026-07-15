from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence
from ai_web_explorer.grounded_web.typed_delta import (
    observed_deltas_from_typed,
    typed_deltas_from_facts,
)


def test_typed_deltas_from_facts_preserves_type_and_evidence():
    evidence = [StructureEvidence(source="dom_indicator", selector="#count")]
    before = [
        AbstractStateFact(
            fact_id="result_count",
            fact_type="numeric",
            value=0,
            identity_role="identity",
            source_ref="result-count",
            evidence=evidence,
        )
    ]
    after = [
        AbstractStateFact(
            fact_id="result_count",
            fact_type="numeric",
            value=3,
            identity_role="identity",
            source_ref="result-count",
            evidence=evidence,
        )
    ]

    deltas = typed_deltas_from_facts(before, after)
    observed = observed_deltas_from_typed(
        deltas,
        url="https://example.test/search",
    )

    assert deltas[0].delta_type == "numeric_changed"
    assert deltas[0].identity_relevant is True
    assert observed[0].field == "result_count"
    assert observed[0].delta_type == "numeric_changed"
    assert observed[0].evidence[0].selector == "#count"
