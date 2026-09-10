from backend.rubric_loader import load_rubric


def test_hld_dimension_set():
    rubric = load_rubric("hld")
    assert set(rubric.dimension_names()) == {
        "requirements_clarification",
        "capacity_estimation",
        "high_level_design",
        "deep_dive",
        "tradeoffs_stated",
        "failure_modes",
    }
    assert rubric.version == "hld_v1"
    assert rubric.round_type == "hld"


def test_lld_deepdive_is_a_distinct_stub():
    rubric = load_rubric("lld_deepdive")
    assert rubric.version == "lld_deepdive_v1"
    # Stubbed pending Flagged item 2 - must not silently inherit HLD's dimensions.
    assert set(rubric.dimension_names()) != set(load_rubric("hld").dimension_names())
