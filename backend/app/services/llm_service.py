from __future__ import annotations
import inspect
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import get_settings, reset_settings_cache
import logging
import os

logger = logging.getLogger(__name__)


class LLMService:
    @staticmethod
    def _is_valid_value(value: Optional[str]) -> bool:
        if value is None:
            return False
        text = str(value).strip()
        if not text:
            return False
        lowered = text.lower()
        placeholder_tokens = {
            "enter your azure openai api key here",
            "enter your azure openai endpoint here",
            "enter your azure openai deployment here",
            "enter your azure openai api version here",
            "your_openai_api_key_here",
            "<your-resource-name>",
            "<your-deployment-name>",
            "example",
            "placeholder",
            "changeme",
        }
        if lowered in placeholder_tokens:
            return False
        if lowered.startswith("enter your ") and lowered.endswith(" here"):
            return False
        if "<your-" in lowered or "<resource" in lowered:
            return False
        return True

    @staticmethod
    def _provider() -> str:
        reset_settings_cache()
        settings = get_settings()

        env_provider = (os.environ.get("LLM_PROVIDER") or "").upper()
        azure_key = os.environ.get("AZURE_OPENAI_API_KEY") or settings.azure_openai_api_key
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or settings.azure_openai_endpoint
        azure_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or settings.azure_openai_deployment
        azure_ready = bool(
            LLMService._is_valid_value(azure_key)
            and LLMService._is_valid_value(azure_endpoint)
            and LLMService._is_valid_value(azure_deployment)
        )
        gemini_ready = bool(LLMService._is_valid_value(os.environ.get("GEMINI_API_KEY") or settings.gemini_api_key))
        openai_ready = bool(LLMService._is_valid_value(os.environ.get("OPENAI_API_KEY") or settings.openai_api_key))

        if env_provider in {"AZURE_OPENAI", "AZURE"}:
            return "AZURE_OPENAI" if azure_ready else ("GEMINI" if gemini_ready else "OPENAI")
        if env_provider == "GEMINI":
            return "GEMINI" if gemini_ready else "OPENAI"
        if env_provider == "OPENAI":
            return "OPENAI" if openai_ready else ("GEMINI" if gemini_ready else "AZURE_OPENAI" if azure_ready else "OPENAI")

        if azure_ready:
            return "AZURE_OPENAI"
        if gemini_ready:
            return "GEMINI"
        if openai_ready:
            return "OPENAI"

        prov = (settings.llm_provider or "").upper()
        if prov in {"AZURE_OPENAI", "AZURE"} and azure_ready:
            return "AZURE_OPENAI"
        if prov == "GEMINI" and gemini_ready:
            return "GEMINI"
        if prov == "OPENAI" and openai_ready:
            return "OPENAI"
        return "AZURE_OPENAI" if azure_ready else "OPENAI"

    @staticmethod
    def is_configured() -> bool:
        reset_settings_cache()
        settings = get_settings()
        prov = LLMService._provider()
        if prov == "AZURE_OPENAI":
            azure_key = os.environ.get("AZURE_OPENAI_API_KEY") or settings.azure_openai_api_key
            azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or settings.azure_openai_endpoint
            azure_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or settings.azure_openai_deployment
            return all(LLMService._is_valid_value(v) for v in (azure_key, azure_endpoint, azure_deployment))
        if prov == "GEMINI":
            return LLMService._is_valid_value(os.environ.get("GEMINI_API_KEY") or settings.gemini_api_key)
        return LLMService._is_valid_value(os.environ.get("OPENAI_API_KEY") or settings.openai_api_key)

    @staticmethod
    def _call_api(payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        reset_settings_cache()
        settings = get_settings()
        prov = LLMService._provider()
        if prov == "AZURE_OPENAI":
            api_key = os.environ.get("AZURE_OPENAI_API_KEY") or settings.azure_openai_api_key
            base = (os.environ.get("AZURE_OPENAI_ENDPOINT") or settings.azure_openai_endpoint).rstrip("/")
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or settings.azure_openai_deployment
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION") or settings.azure_openai_api_version
            if not api_key or not base or not deployment:
                raise RuntimeError("Azure OpenAI credentials not configured")
            headers = {"api-key": api_key, "Content-Type": "application/json"}
            url = f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        elif prov == "GEMINI":
            api_key = os.environ.get("GEMINI_API_KEY") or settings.gemini_api_key
            base = (os.environ.get("GEMINI_BASE_URL") or settings.gemini_base_url).rstrip("/")
            if not api_key:
                raise RuntimeError("Gemini API key not configured")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            model = os.environ.get("GEMINI_MODEL") or settings.gemini_model
            url = f"{base}/v1beta/models/{model}:generateContent"
        else:
            api_key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
            base = (os.environ.get("OPENAI_BASE_URL") or settings.openai_base_url).rstrip("/")
            if not api_key:
                raise RuntimeError("OpenAI API key not configured")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            url = f"{base}/chat/completions"
        try:
            kwargs: Dict[str, Any] = {"headers": headers, "json": payload, "timeout": timeout}
            if "trust_env" in inspect.signature(httpx.post).parameters:
                kwargs["trust_env"] = False
            resp = httpx.post(url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("LLM API call failed: %s", exc)
            raise

    @staticmethod
    def chat(messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.0) -> str:
        reset_settings_cache()
        settings = get_settings()
        prov = LLMService._provider()
        if prov == "GEMINI":
            model = model or os.environ.get("GEMINI_MODEL") or settings.gemini_model
            contents = []
            for msg in messages:
                role = (msg.get("role") or "user").lower()
                text = str(msg.get("content") or "")
                if role == "system":
                    contents.append({"role": "user", "parts": [{"text": f"System instruction: {text}"}]})
                else:
                    contents.append({"role": role, "parts": [{"text": text}]})
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 512,
                },
                "model": model,
            }
        else:
            if prov == "AZURE_OPENAI":
                model = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT") or settings.azure_openai_deployment
                payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": 512}
            else:
                model = model or os.environ.get("OPENAI_MODEL") or settings.openai_model
                payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": 512}
        data = LLMService._call_api(payload)
        try:
            if isinstance(data, dict) and data.get("choices"):
                choice = data.get("choices", [])[0]
                if "message" in choice:
                    return choice["message"].get("content", "")
                return choice.get("text", "")
            if isinstance(data, dict) and data.get("candidates"):
                candidate = data["candidates"][0]
                parts = candidate.get("content", {}).get("parts", []) if isinstance(candidate, dict) else []
                if isinstance(parts, list):
                    texts = []
                    for part in parts:
                        if isinstance(part, dict) and part.get("text"):
                            texts.append(str(part["text"]))
                    if texts:
                        return "".join(texts)
                return str(candidate)
            if isinstance(data, dict) and data.get("outputs"):
                out = data.get("outputs")[0]
                if isinstance(out, dict) and out.get("content"):
                    c = out.get("content")
                    if isinstance(c, list) and c:
                        return c[0].get("text", "") if isinstance(c[0], dict) else str(c[0])
                    return str(c)
            return str(data)
        except Exception:
            return ""

    @staticmethod
    def summarize_execution(execution_metadata: Dict[str, Any]) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": "You are a deterministic execution analyst. Provide a concise summary and action plan."},
            {"role": "user", "content": f"Execution metadata:\n{execution_metadata}"},
        ]
        text = LLMService.chat(messages, temperature=0.0)
        return {"agent_summary": text}

    @staticmethod
    def analyze_verification(structured_diff: Any, legacy: Any = None, modern: Any = None) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": "You are a verification analyst. Explain differences and propose root causes and remediation steps."},
            {"role": "user", "content": f"Structured diff:\n{structured_diff}\nLegacy:\n{legacy}\nModern:\n{modern}"},
        ]
        text = LLMService.chat(messages, temperature=0.0)
        return {"agent_report": text}

    @staticmethod
    def explain(verification_inputs: Dict[str, Any], graph: Any = None) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": "You are an expert software engineer. Given verification inputs and a dependency graph, provide root cause analysis and step-by-step remediation."},
            {"role": "user", "content": f"Verification inputs:\n{verification_inputs}\nGraph:\n{graph}"},
        ]
        text = LLMService.chat(messages, temperature=0.0)
        return {"agent_explain": text}
