"""AWS Bedrock adapter for Nexra SDK.

Provides a SigV4-compatible bridge for Bedrock agents to interact with Nexra.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("nexra_sdk.adapters.bedrock")


class BedrockNexraBridge:
    """Bridge between AWS Bedrock agents and Nexra.

    Translates Bedrock agent action group requests into Nexra API calls.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    async def handle_action_group(self, event: dict) -> dict:
        """Handle a Bedrock agent action group invocation.

        Maps Bedrock action names to Nexra SDK methods.
        """
        action = event.get("actionGroup", "")
        api_path = event.get("apiPath", "")
        parameters = event.get("parameters", [])
        request_body = event.get("requestBody", {}).get("content", {}).get(
            "application/json", {}
        )

        params = {p["name"]: p["value"] for p in parameters}

        if api_path == "/discover":
            matches = await self.client.discover(
                query=params.get("query", ""),
                limit=int(params.get("limit", 5)),
            )
            return self._bedrock_response(
                200,
                [
                    {"agent_id": m.agent_id, "name": m.name, "match_score": m.match_score}
                    for m in matches
                ],
            )

        elif api_path == "/delegate":
            body = request_body.get("properties", request_body)
            result = await self.client.delegate(
                agent_id=body.get("agent_id", ""),
                task=body.get("task", {}),
                budget_cap=float(body.get("budget_cap", 1.0)),
            )
            return self._bedrock_response(
                200,
                {
                    "delegation_id": result.delegation_id,
                    "status": result.status,
                    "result": result.result,
                },
            )

        return self._bedrock_response(400, {"error": f"Unknown API path: {api_path}"})

    def _bedrock_response(self, status_code: int, body: Any) -> dict:
        return {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": "NexraActions",
                "apiPath": "/response",
                "httpMethod": "POST",
                "httpStatusCode": status_code,
                "responseBody": {
                    "application/json": {"body": json.dumps(body)}
                },
            },
        }
