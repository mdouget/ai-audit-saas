from app.scoring import Answer, calculate, DOMAIN_WEIGHTS

def test_unknown_withholds_score():
    result = calculate([Answer(domain=d, status="unknown") for d in DOMAIN_WEIGHTS])
    assert result["overall_score"] is None
    assert all(x["coverage"] == 0 for x in result["domains"].values())

def test_full_coverage_scores_correctly():
    assert calculate([Answer(domain=d, status="validated") for d in DOMAIN_WEIGHTS])["overall_score"] == 100

def test_partial_coverage_cannot_produce_misleading_overall():
    answers = [Answer(domain=d, status="validated") for d in DOMAIN_WEIGHTS]
    answers.append(Answer(domain="security", status="unknown"))
    result = calculate(answers)
    assert result["overall_score"] is None
    assert result["domains"]["security"]["coverage"] == 50

def test_not_applicable_excluded():
    answers = [Answer(domain=d, status="implemented") for d in DOMAIN_WEIGHTS]
    answers.append(Answer(domain="governance", status="not_applicable"))
    assert calculate(answers)["overall_score"] == 75
