from dashboard.app import monthly_chart, quick_read_text


def test_monthly_chart_keeps_months_categorical():
    figure = monthly_chart({"2026-06": 100, "2026-07": 200, "2026-08": 300})

    assert list(figure.data[0].x) == ["Jun 2026", "Jul 2026", "Aug 2026"]
    assert figure.layout.xaxis.type == "category"
    assert list(figure.layout.xaxis.categoryarray) == ["Jun 2026", "Jul 2026", "Aug 2026"]


def test_quick_read_uses_debit_categories_and_income():
    text = quick_read_text(
        {"total_spending": 26220, "total_credit": 45000, "net_cash_flow": 18780},
        {"categories": {"Food": 3400}},
    )

    assert "Food is your largest spending category at ₹3,400." in text
    assert "Income of ₹45,000 exceeds spending by ₹18,780." in text
