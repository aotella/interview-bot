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


def test_lld_deepdive_dimension_set():
    rubric = load_rubric("lld_deepdive")
    assert set(rubric.dimension_names()) == {
        "requirements_clarification",
        "class_and_interface_design",
        "concurrency_and_edge_cases",
        "extensibility_tradeoffs",
        "deep_dive_depth",
        "communication_of_tradeoffs",
    }
    assert rubric.version == "lld_deepdive_v1"
    assert rubric.round_type == "lld_deepdive"
    # Tailored to its own two-halves framing, not inherited from HLD by analogy.
    assert set(rubric.dimension_names()) != set(load_rubric("hld").dimension_names())
