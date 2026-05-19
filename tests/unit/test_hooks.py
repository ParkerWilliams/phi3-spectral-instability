"""Tests for ``phi3geom.extraction.hooks``.

Uses a tiny synthetic attention module (``synthetic_phi3_attention_module``
fixture from ``tests/unit/conftest.py``) so these tests don't require
real Phi-3 weights or a CUDA device.

The torch import is lazy: this file imports torch at top level because
torch is a runtime dep declared in pyproject.toml. On a machine without
torch installed, the test file fails to collect — which is the correct
behavior (the module under test fundamentally needs torch).
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch", reason="torch is a runtime dep; install with -e '.'")

from phi3geom.extraction.hooks import Phi3ExtractionHook, recover_qkt_avwo  # noqa: E402


class _ToyModelWrapper(torch.nn.Module):
    """Wraps the tiny attention module to look like Phi-3's nested structure:
    ``wrapper.model.layers[i].self_attn`` for the hook walker.
    """

    def __init__(self, attn_modules: list[torch.nn.Module]) -> None:
        super().__init__()

        class _Layer(torch.nn.Module):
            def __init__(self, attn: torch.nn.Module) -> None:
                super().__init__()
                self.self_attn = attn

            def forward(self, x: "torch.Tensor") -> "torch.Tensor":
                return self.self_attn(x)

        class _Inner(torch.nn.Module):
            def __init__(self, layers_: list[torch.nn.Module]) -> None:
                super().__init__()
                self.layers = torch.nn.ModuleList(layers_)

            def forward(self, x: "torch.Tensor") -> "torch.Tensor":
                for layer in self.layers:
                    x = layer(x)
                return x

        self.model = _Inner([_Layer(m) for m in attn_modules])

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        return self.model(x)


def _make_attn_with_attrs(d_model: int = 32, n_heads: int = 4) -> torch.nn.Module:
    """A toy attention module with the attributes our hooks expect."""

    class TinyAttnWithAttrs(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.config = type("C", (), {"num_attention_heads": n_heads})()
            self.d_head = d_model // n_heads
            self.qkv_proj = torch.nn.Linear(d_model, 3 * d_model, bias=False)
            self.o_proj = torch.nn.Linear(d_model, d_model, bias=False)

        def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor | None]:
            b, t, _ = x.shape
            qkv = self.qkv_proj(x).reshape(b, t, 3, n_heads, self.d_head)
            q, k, v = qkv.unbind(dim=2)
            scores = torch.einsum("bthd,bThd->bhtT", q, k) / (self.d_head**0.5)
            attn = torch.softmax(scores, dim=-1)
            ctx = torch.einsum("bhtT,bThd->bthd", attn, v).reshape(b, t, d_model)
            return self.o_proj(ctx), attn  # tuple form: (hidden, attn_weights)

    torch.manual_seed(0)
    return TinyAttnWithAttrs()


def test_hook_captures_qkv_per_layer() -> None:
    layer0 = _make_attn_with_attrs()
    layer1 = _make_attn_with_attrs()
    model = _ToyModelWrapper([layer0, layer1])
    model.eval()

    x = torch.randn(1, 5, 32)
    with Phi3ExtractionHook(model) as hook:
        _ = model(x)

    assert set(hook.captures.keys()) == {0, 1}
    for cap in hook.captures.values():
        assert cap.q is not None and cap.k is not None and cap.v is not None
        assert cap.q.shape == (1, 5, 4, 8)
        assert cap.attention_weights is not None
        assert cap.attention_weights.shape == (1, 4, 5, 5)
        assert cap.o_weight is not None
        assert cap.o_weight.shape == (32, 32)


def test_hook_handles_are_removed_on_exit() -> None:
    layer0 = _make_attn_with_attrs()
    model = _ToyModelWrapper([layer0])
    model.eval()

    with Phi3ExtractionHook(model) as hook:
        x = torch.randn(1, 4, 32)
        _ = model(x)
    # After context exit, the qkv_proj should have no remaining forward hooks.
    # PyTorch stores hooks in `_forward_hooks` (an OrderedDict).
    assert len(layer0.qkv_proj._forward_hooks) == 0


def test_recover_qkt_avwo_shapes_and_dtype() -> None:
    layer0 = _make_attn_with_attrs(d_model=32, n_heads=4)
    model = _ToyModelWrapper([layer0])
    model.eval()
    x = torch.randn(1, 5, 32)

    with Phi3ExtractionHook(model) as hook:
        _ = model(x)
    cap = hook.captures[0]
    qkt, avwo = recover_qkt_avwo(cap, head_idx=2, token_idx=3)
    assert qkt.shape == (8, 8)
    assert avwo.shape == (8, 8)
    assert qkt.dtype == torch.float64
    assert avwo.dtype == torch.float64


def test_recover_raises_on_incomplete_capture() -> None:
    from phi3geom.extraction.hooks import LayerCapture
    cap = LayerCapture()  # all None
    with pytest.raises(RuntimeError, match="Capture incomplete"):
        recover_qkt_avwo(cap, head_idx=0, token_idx=0)
