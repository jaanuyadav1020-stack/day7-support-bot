import pytest
import logging
import re

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_root_returns_api_information(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_json()["chat_endpoint"] == "/chat"


def test_chat_returns_a_reply(client):
    response = client.post("/chat", json={"customer_email": "ravi.kumar@example.com", "message": "Hello"})
    assert response.status_code == 200
    assert "reply" in response.get_json()


def test_order_status(client):
    response = client.post("/chat", json={"customer_email": "ravi.kumar@example.com", "message": "Where is my order 10231?"})
    assert response.get_json()["action_result"] == "Shipped"


def test_unknown_order(client):
    response = client.post("/chat", json={"customer_email": "priya.s@example.com", "message": "What is the status of order 99999?"})
    assert response.get_json()["action_result"] == "Order not found"


def test_account_deletion_requires_confirmation(client):
    response = client.post(
        "/chat",
        json={
            "customer_email": "ravi.kumar@example.com",
            "message": "Close my account",
        },
    )
    assert response.status_code == 200
    assert response.get_json()["action_result"] == (
        "Account deletion rejected: human confirmation required"
    )


def test_refund_rejects_unknown_order(client):
    response = client.post(
        "/chat",
        json={
            "customer_email": "ravi.kumar@example.com",
            "message": "Refund order 99999 Rs 100",
        },
    )
    assert response.get_json()["action_result"] == (
        "Refund rejected: order not found"
    )


def test_refund_rejects_amount_above_order_value(client):
    response = client.post(
        "/chat",
        json={
            "customer_email": "ravi.kumar@example.com",
            "message": "Refund order 10232 Rs 500",
        },
    )
    assert response.get_json()["action_result"] == (
        "Refund rejected: amount exceeds order value"
    )


def test_ai_call_log_contains_metrics_without_personal_data(client, caplog):
    caplog.set_level(logging.INFO)
    customer_email = "ravi.kumar@example.com"
    message = "Where is my order 10231?"

    client.post(
        "/chat",
        json={"customer_email": customer_email, "message": message},
    )

    ai_lines = [record.getMessage() for record in caplog.records if "AI_CALL" in record.getMessage()]
    assert len(ai_lines) == 1
    ai_line = ai_lines[0]
    assert re.search(r"request_id=[0-9a-f-]{36}", ai_line)
    assert "model=fake-support-model" in ai_line
    assert re.search(r"latency_ms=\d+\.\d{2}", ai_line)
    assert re.search(r"input_tokens=\d+", ai_line)
    assert re.search(r"output_tokens=\d+", ai_line)
    assert re.search(r"estimated_cost_rs=\d+\.\d{4}", ai_line)
    assert customer_email not in ai_line
    assert message not in ai_line
