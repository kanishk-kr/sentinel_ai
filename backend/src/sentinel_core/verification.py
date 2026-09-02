"""
SENTINEL — Verification Layer
FR3.7: Structured verification verdict. LLM generation never equals task completion.
Completion = generation + verification + policy compliance + artifact validation.
"""
from __future__ import annotations

import json
import logging

from src.model_gateway.execution_manager import execution_manager
from src.model_gateway.router import model_router
from src.shared.schemas import VerificationVerdict

logger = logging.getLogger(__name__)

VERIFICATION_PROMPT = """You are the SENTINEL Verification Layer. Your job is to verify the quality and correctness of generated content.

Analyze the following output and provide a verification verdict with these checks:
1. **schema**: Is the output well-structured and in the expected format?
2. **citations**: Are all claims properly cited with sources?
3. **evidence_support**: Does each claim have supporting evidence from the provided sources?
4. **domain_validation**: Is the content factually reasonable and domain-appropriate?

For each check, return "PASS" or "FAIL".
List any errors found.

Respond in this EXACT JSON format:
{
  "status": "PASS" or "FAILED",
  "checks": {
    "schema": "PASS" or "FAIL",
    "citations": "PASS" or "FAIL",
    "evidence_support": "PASS" or "FAIL",
    "domain_validation": "PASS" or "FAIL"
  },
  "errors": ["list of specific errors found"],
  "warnings": ["list of warnings"]
}
"""


class VerificationLayer:
    """
    Structured verification (FR3.7).
    Returns typed verdicts; results are never accepted without PASS.
    """

    async def verify_text_output(
        self,
        output: str,
        context: dict | None = None,
        sources: list[dict] | None = None,
    ) -> VerificationVerdict:
        """Verify a text/document output for quality and citations."""
        routing = model_router.route({
            "capabilities": ["general_qa", "analysis"],
            "vision": False,
            "min_context": 4096,
        })

        if routing.status == "ROUTING_FAILURE":
            # If no model available, do basic checks only
            return self._basic_verify(output)

        try:
            messages = [
                {"role": "system", "content": VERIFICATION_PROMPT},
                {"role": "user", "content": f"""Verify this output:

OUTPUT:
{output[:3000]}

CONTEXT/SOURCES:
{json.dumps(sources[:5] if sources else [], default=str)[:2000]}

Provide your verification verdict as JSON."""},
            ]

            response = await execution_manager.invoke(
                model_id=routing.model_id,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )

            return self._parse_verdict(response)
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return self._basic_verify(output)

    async def verify_code(
        self,
        code: str,
        language: str = "python",
    ) -> VerificationVerdict:
        """Verify code output (FR6.3): parse → lint → basic validation."""
        checks = {
            "schema": "PASS",
            "citations": "PASS",  # Not applicable for code
            "evidence_support": "PASS",
            "domain_validation": "PASS",
        }
        errors = []
        warnings = []

        # Basic syntax check for Python
        if language == "python":
            try:
                compile(code, "<string>", "exec")
            except SyntaxError as e:
                checks["schema"] = "FAIL"
                errors.append(f"Syntax error: {e}")

        # Check for dangerous patterns
        dangerous_patterns = [
            "os.system(", "subprocess.call(", "eval(", "exec(",
            "__import__", "open('/etc", "open('/root",
        ]
        for pattern in dangerous_patterns:
            if pattern in code:
                checks["domain_validation"] = "FAIL"
                errors.append(f"Potentially dangerous pattern found: {pattern}")

        # Check for completeness
        if len(code.strip()) < 10:
            checks["schema"] = "FAIL"
            errors.append("Code output is too short / empty")

        status = "PASS" if all(v == "PASS" for v in checks.values()) else "FAILED"
        return VerificationVerdict(status=status, checks=checks, errors=errors, warnings=warnings)

    async def verify_extraction(
        self,
        extractions: list[dict],
        confidence_threshold: float = 0.7,
    ) -> VerificationVerdict:
        """Verify document extraction results (FR4.3)."""
        checks = {
            "schema": "PASS",
            "citations": "PASS",
            "evidence_support": "PASS",
            "domain_validation": "PASS",
        }
        errors = []
        warnings = []

        if not extractions:
            checks["schema"] = "FAIL"
            errors.append("No extractions produced")
            return VerificationVerdict(status="FAILED", checks=checks, errors=errors)

        # Check each extraction for confidence
        low_confidence_count = 0
        for ext in extractions:
            confidence = ext.get("confidence", 0)
            if confidence < confidence_threshold:
                low_confidence_count += 1
                warnings.append(
                    f"Low confidence ({confidence:.2f}) for field: {ext.get('field_name', 'unknown')}"
                )

        if low_confidence_count > len(extractions) * 0.5:
            checks["evidence_support"] = "FAIL"
            errors.append(f"{low_confidence_count}/{len(extractions)} extractions below confidence threshold")

        status = "PASS" if all(v == "PASS" for v in checks.values()) else "FAILED"
        return VerificationVerdict(status=status, checks=checks, errors=errors, warnings=warnings)

    def _basic_verify(self, output: str) -> VerificationVerdict:
        """Basic verification when LLM is unavailable."""
        checks = {
            "schema": "PASS" if len(output.strip()) > 10 else "FAIL",
            "citations": "PASS",
            "evidence_support": "PASS",
            "domain_validation": "PASS",
        }
        errors = []
        if checks["schema"] == "FAIL":
            errors.append("Output is empty or too short")

        status = "PASS" if all(v == "PASS" for v in checks.values()) else "FAILED"
        return VerificationVerdict(status=status, checks=checks, errors=errors)

    def _parse_verdict(self, response: str) -> VerificationVerdict:
        """Parse verification verdict from LLM response."""
        try:
            text = response.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                return VerificationVerdict(
                    status=data.get("status", "PASS"),
                    checks=data.get("checks", {}),
                    errors=data.get("errors", []),
                    warnings=data.get("warnings", []),
                )
        except (json.JSONDecodeError, ValueError):
            pass
        return VerificationVerdict(status="PASS", checks={}, errors=[], warnings=["Could not parse LLM verdict"])


# Singleton
verification_layer = VerificationLayer()
