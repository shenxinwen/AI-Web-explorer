from ai_web_explorer.grounded_web.state_facts import (
    facts_from_structure,
    state_signature_from_facts,
)
from ai_web_explorer.grounded_web.structure import (
    IndicatorObservation,
    PageInfo,
    PageStructureObservation,
    RegionObservation,
    RepeatedGroupObservation,
    StructureEvidence,
)


def test_facts_from_structure_derives_typed_identity_facts():
    evidence = [StructureEvidence(source="dom", selector='[data-state="count"]')]
    observation = PageStructureObservation(
        page=PageInfo(
            url="https://example.test/search?q=abc",
            title="Search",
            page_id="search",
        ),
        regions=[
            RegionObservation(
                id="results",
                role="status",
                label="Results",
                visible=True,
                locator='[role="status"]',
                evidence=evidence,
            )
        ],
        indicators=[
            IndicatorObservation(
                id="result-count",
                indicator_type="numeric",
                key_hint="result-count",
                value=3,
                visible=True,
                locator='[data-state="result-count"]',
                evidence=evidence,
            )
        ],
        repeated_groups=[
            RepeatedGroupObservation(
                id="result-row",
                pattern_hint="result-row",
                count=3,
                representative_locator='[data-entity-type="result-row"]',
                evidence=evidence,
            )
        ],
    )

    facts = facts_from_structure(observation)
    signature = state_signature_from_facts(facts)

    assert signature["url_path"] == "/search"
    assert signature["results_visible"] is True
    assert signature["result_count"] == 3
    assert signature["result_row_count"] == 3
    assert {fact.fact_type for fact in facts} >= {
        "navigation",
        "visibility",
        "numeric",
        "repeated_entity_count",
    }
