"""
LLM Provider — 统一的 LLM 调用抽象层。

支持本地 Ollama + 多云端 API，一个接口调所有。
agenticSeek 支持 7 个 Provider，MCR 也要有。

用法:
    provider = LLMProvider()
    response = provider.chat("你好", model="ollama:qwen2.5:7b")
    response = provider.chat("你好", model="deepseek:deepseek-chat")
    response = provider.chat("你好")  # 用默认模型
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Generator

CONFIG_PATH = Path(__file__).parent.parent / "config" / "llm_providers.json"


class LLMProvider:
    """统一 LLM 调用接口。"""

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path or CONFIG_PATH)
        self.default_model = self.config.get("default_model", "ollama:qwen2.5:7b")

    def _load_config(self, path) -> dict:
        """加载 Provider 配置。"""
        if isinstance(path, str):
            path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        # 默认配置
        return {
            "default_model": "ollama:qwen2.5:7b",
            "providers": {
                "ollama": {
                    "type": "ollama",
                    "base_url": "http://localhost:11434",
                    "models": ["qwen2.5:7b", "qwen2.5:14b", "llama3.1:8b", "deepseek-coder:6.7b"]
                },
                "deepseek": {
                    "type": "openai_compatible",
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "models": ["deepseek-chat", "deepseek-coder"]
                },
                "openai": {
                    "type": "openai_compatible",
                    "base_url": "https://api.openai.com/v1",
                    "api_key_env": "OPENAI_API_KEY",
                    "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
                },
                "anthropic": {
                    "type": "anthropic",
                    "base_url": "https://api.anthropic.com/v1",
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "models": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
                },
                "local": {
                    "type": "openai_compatible",
                    "base_url": "http://localhost:8080/v1",
                    "api_key_env": None,
                    "models": ["local-model"]
                }
            }
        }

    def chat(self, prompt: str, model: Optional[str] = None, system: str = "",
             temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """
        发送聊天请求，返回文本响应。

        model 格式: "provider:model_name" 或 "provider:model_name:variant"
        例如: "ollama:qwen2.5:7b", "deepseek:deepseek-chat"
        """
        model = model or self.default_model
        provider_name, model_name = self._parse_model(model)
        provider_config = self._get_provider(provider_name)

        if provider_config["type"] == "ollama":
            return self._call_ollama(provider_config, model_name, prompt, system, temperature, max_tokens)
        elif provider_config["type"] == "openai_compatible":
            return self._call_openai_compatible(provider_config, model_name, prompt, system, temperature, max_tokens)
        elif provider_config["type"] == "anthropic":
            return self._call_anthropic(provider_config, model_name, prompt, system, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider type: {provider_config['type']}")

    def chat_stream(self, prompt: str, model: Optional[str] = None, system: str = "",
                    temperature: float = 0.7, max_tokens: int = 2048) -> Generator[str, None, None]:
        """流式输出。"""
        model = model or self.default_model
        provider_name, model_name = self._parse_model(model)
        provider_config = self._get_provider(provider_name)

        if provider_config["type"] == "ollama":
            yield from self._stream_ollama(provider_config, model_name, prompt, system, temperature, max_tokens)
        elif provider_config["type"] == "openai_compatible":
            yield from self._stream_openai_compatible(provider_config, model_name, prompt, system, temperature, max_tokens)
        else:
            # 回退到非流式
            yield self.chat(prompt, model, system, temperature, max_tokens)

    def list_models(self) -> list:
        """列出所有可用模型。"""
        models = []
        for provider_name, provider_config in self.config.get("providers", {}).items():
            for model in provider_config.get("models", []):
                models.append(f"{provider_name}:{model}")
        return models

    def health_check(self) -> dict:
        """检查所有 Provider 的健康状态。"""
        results = {}
        for provider_name, provider_config in self.config.get("providers", {}).items():
            try:
                if provider_config["type"] == "ollama":
                    url = f"{provider_config['base_url']}/api/tags"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read())
                        results[provider_name] = {
                            "status": "ok",
                            "models": [m["name"] for m in data.get("models", [])]
                        }
                elif provider_config["type"] == "openai_compatible":
                    key_env = provider_config.get("api_key_env")
                    if not key_env:
                        # No API key needed (local server)
                        results[provider_name] = {"status": "configured", "note": "no_auth"}
                    else:
                        api_key = os.environ.get(key_env, "")
                        if not api_key:
                            results[provider_name] = {"status": "no_api_key"}
                        else:
                            results[provider_name] = {"status": "configured"}
                elif provider_config["type"] == "anthropic":
                    api_key = os.environ.get(provider_config.get("api_key_env", ""), "")
                    if not api_key:
                        results[provider_name] = {"status": "no_api_key"}
                    else:
                        results[provider_name] = {"status": "configured"}
            except Exception as e:
                results[provider_name] = {"status": "error", "error": str(e)[:100]}
        return results

    # ═══ 内部方法 ═══

    def _parse_model(self, model: str) -> tuple:
        """解析 'provider:model' 格式。"""
        parts = model.split(":", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        # 没有 provider 前缀，用默认
        return "ollama", model

    def _get_provider(self, name: str) -> dict:
        """获取 Provider 配置。"""
        providers = self.config.get("providers", {})
        if name not in providers:
            raise ValueError(f"Unknown provider: {name}. Available: {list(providers.keys())}")
        return providers[name]

    def _call_ollama(self, config: dict, model: str, prompt: str, system: str,
                     temperature: float, max_tokens: int) -> str:
        """调用 Ollama API。"""
        url = f"{config['base_url']}/api/chat"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("message", {}).get("content", "")

    def _stream_ollama(self, config: dict, model: str, prompt: str, system: str,
                       temperature: float, max_tokens: int) -> Generator[str, None, None]:
        """Ollama 流式输出。"""
        url = f"{config['base_url']}/api/chat"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                line = line.decode("utf-8").strip()
                if line:
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        pass

    def _call_openai_compatible(self, config: dict, model: str, prompt: str, system: str,
                                temperature: float, max_tokens: int) -> str:
        """调用 OpenAI 兼容 API。"""
        api_key = os.environ.get(config.get("api_key_env", ""), "")
        if not api_key:
            raise ValueError(f"No API key. Set {config.get('api_key_env')} environment variable.")

        url = f"{config['base_url']}/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def _stream_openai_compatible(self, config: dict, model: str, prompt: str, system: str,
                                  temperature: float, max_tokens: int) -> Generator[str, None, None]:
        """OpenAI 兼容 API 流式输出。"""
        api_key = os.environ.get(config.get("api_key_env", ""), "")
        if not api_key:
            raise ValueError(f"No API key. Set {config.get('api_key_env')} environment variable.")

        url = f"{config['base_url']}/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                line = line.decode("utf-8").strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        pass

    def _call_anthropic(self, config: dict, model: str, prompt: str, system: str,
                        temperature: float, max_tokens: int) -> str:
        """调用 Anthropic API。"""
        api_key = os.environ.get(config.get("api_key_env", ""), "")
        if not api_key:
            raise ValueError(f"No API key. Set {config.get('api_key_env')} environment variable.")

        url = f"{config['base_url']}/messages"
        messages = [{"role": "user", "content": prompt}]

        payload = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system or "You are a helpful assistant.",
            "messages": messages
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            content_blocks = data.get("content", [])
            return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")


# ═══ CLI ═══

def main():
    import argparse
    parser = argparse.ArgumentParser(description="MCR LLM Provider")
    sub = parser.add_subparsers(dest="command")

    p_chat = sub.add_parser("chat", help="Send a chat request")
    p_chat.add_argument("prompt", help="The prompt")
    p_chat.add_argument("--model", default=None, help="Model (provider:name)")
    p_chat.add_argument("--system", default="", help="System prompt")
    p_chat.add_argument("--temperature", type=float, default=0.7)
    p_chat.add_argument("--max-tokens", type=int, default=2048)

    sub.add_parser("models", help="List available models")
    sub.add_parser("health", help="Check provider health")

    args = parser.parse_args()
    provider = LLMProvider()

    if args.command == "chat":
        response = provider.chat(args.prompt, model=args.model, system=args.system,
                                 temperature=args.temperature, max_tokens=args.max_tokens)
        print(response)
    elif args.command == "models":
        models = provider.list_models()
        print(json.dumps(models, indent=2, ensure_ascii=False))
    elif args.command == "health":
        health = provider.health_check()
        print(json.dumps(health, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
