from scripts.paper.plot_c2 import mean_padded_curves


def test_mean_padded_curves_extends_shorter_runs_to_common_budget():
    result = mean_padded_curves([[1, 2], [1, 1, 3]], budget=4)

    assert result == [1.0, 1.5, 2.5, 2.5]
