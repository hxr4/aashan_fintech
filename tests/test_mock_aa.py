import asyncio

from app.services.mock_aa import MockAAProvider, generate_mock_transactions


def test_mock_aa_flow():
    asyncio.run(_test_mock_aa_flow())


async def _test_mock_aa_flow():
    provider = MockAAProvider()
    consent = await provider.create_consent({"purpose": "demo"})
    assert consent["status"] == "PENDING"
    approved = await provider.approve_consent(consent["id"])
    assert approved["status"] == "ACTIVE"
    session = await provider.create_data_session(consent["id"])
    assert session["status"] == "READY"
    data = await provider.fetch_data(session["id"])
    assert len(data) >= 50
    assert all("MOCK / DEMO DATA" in row["description"] for row in data)
