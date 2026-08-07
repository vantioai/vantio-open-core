# LlamaIndex (Python) + Vantio Optics

LlamaIndex uses `httpx` — use the Python SDK `@shield` decorator (same as LangChain Python).

```bash
pip install vantio-agent-sdk llama-index
```

```python
from llama_index.llms.openai import OpenAI
from vantio import shield

@shield
async def ask(q: str):
    llm = OpenAI(model="gpt-4o-mini")
    return await llm.acomplete(q)
```

Fence: observe / optional Gate PII helpers. Not Absolute Control.
