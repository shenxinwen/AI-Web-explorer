from scripts.paper.plot_c3 import build_plot_data


def test_build_plot_data_converts_formal_metrics_to_percentages():
    metrics = {
        "action_taxonomy": {
            "classification": {"pooled": {"precision": 0.75, "recall": 0.5, "f1": 0.6}},
            "acceptable_type": {"accuracy": 0.25},
        },
        "full": {
            "classification": {"pooled": {"precision": 0.7, "recall": 0.8, "f1": 0.75}},
            "acceptable_type": {"accuracy": 0.65},
        },
    }

    result = build_plot_data(metrics)

    assert result == {
        "Text only": [75.0, 50.0, 60.0, 25.0],
        "Context conditioned": [70.0, 80.0, 75.0, 65.0],
    }
