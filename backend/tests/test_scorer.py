"""Explainable scoring tests (spec §25-28, §63)."""
from app.core.enums import LeadTemperature, RecommendedAction
from app.services.analysis.scorer import LeadScorer, temperature_for


def _score(**kwargs):
    defaults = dict(
        rating=4.0,
        reviews=50,
        website_score=None,
        audit=None,
        has_email=False,
        email_confidence=None,
        has_phone=False,
        has_website=False,
        business_name="Test",
    )
    defaults.update(kwargs)
    return LeadScorer().score(**defaults)


def test_temperature_thresholds():
    assert temperature_for(85) == LeadTemperature.HOT.value
    assert temperature_for(60) == LeadTemperature.WARM.value
    assert temperature_for(45) == LeadTemperature.COLD.value
    assert temperature_for(20) == LeadTemperature.LOW.value


def test_low_confidence_email_never_contact_now():
    result = _score(has_email=True, email_confidence="LOW", rating=4.9, reviews=400, has_website=True,
                    website_score=8.0)
    assert result["recommended_action"] != RecommendedAction.CONTACT_NOW.value


def test_high_confidence_hot_lead_contact_now():
    result = _score(has_email=True, email_confidence="HIGH", has_phone=True, rating=4.8, reviews=327,
                    has_website=True, website_score=6.4, business_name="Clínica X")
    assert result["lead_score"] >= 70
    assert result["temperature"] in (LeadTemperature.HOT.value, LeadTemperature.WARM.value)
    if result["temperature"] == LeadTemperature.HOT.value:
        assert result["recommended_action"] == RecommendedAction.CONTACT_NOW.value


def test_weak_lead_is_low_priority():
    result = _score(rating=3.5, reviews=10)
    assert result["lead_score"] < 60
    assert result["priority"] in ("P3", "P4")


def test_explainable_breakdown():
    result = _score(rating=4.8, reviews=300, has_website=True, website_score=6.0,
                    has_email=True, email_confidence="HIGH", has_phone=True)
    total = sum(item["delta"] for item in result["lead_breakdown"])
    assert total >= result["lead_score"]
    assert all(item["label"] for item in result["lead_breakdown"])


def test_why_this_lead_uses_real_numbers():
    result = _score(rating=4.8, reviews=327, has_website=True, website_score=6.2, business_name="Clínica X")
    assert "327" in result["why_this_lead"]
    assert "Clínica X" in result["why_this_lead"]
