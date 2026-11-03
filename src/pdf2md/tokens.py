"""Contagem de tokens para estimar custo de envio a LLMs."""

from __future__ import annotations

from functools import cache

ENCODING = "o200k_base"


@cache
def _encoder():
    try:
        import tiktoken

        return tiktoken.get_encoding(ENCODING)
    except Exception:  # sem rede no primeiro uso ou tiktoken indisponível
        return None


def count_tokens(text: str) -> tuple[int, str]:
    """Devolve (tokens, método). Sem tiktoken, estima ~4 caracteres por token."""
    enc = _encoder()
    if enc is not None:
        return len(enc.encode(text, disallowed_special=())), f"tiktoken:{ENCODING}"
    return (len(text) + 3) // 4, "estimate:chars/4"
