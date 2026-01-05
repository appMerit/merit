"""AST rewriting for `assert` statements in discovered `merit_*.py` tests.

Merit test modules are loaded via `merit.testing.discovery._load_module`. During that
load, we rewrite `assert` statements so they **do not raise**. Instead, each assert
records an :class:`~merit.assertions.result.AssertionResult` into:

- The current `TEST_CONTEXT` (if present), and
- All metrics in the current `METRICS_CONTEXT` (if present).

While evaluating the assert condition, we also capture:

- Any :class:`~merit.predicates.base.PredicateResult` objects returned from predicate
  calls (sync or async), and
- Any numeric-like attribute reads performed on :class:`~merit.metrics.base.Metric`
  instances (e.g. ``m.mean``).
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

from merit.assertions.result import AssertionResult
from merit.context.context import METRICS_CONTEXT, TEST_CONTEXT
from merit.predicates.base import PredicateResult

if TYPE_CHECKING:
    from merit.metrics.result import MetricResult


def __merit_record_assertion_result(ar: AssertionResult) -> None:
    """Record an assertion result into the active contexts.

    This is invoked by transformed `assert` statements at runtime.
    """

    if (test_ctx := TEST_CONTEXT.get()) is not None:
        test_ctx.collected_assertion_results.append(ar)

    if (metrics := METRICS_CONTEXT.get()) is not None:
        for metric in metrics:
            metric.add_record(ar)


def __merit_capture_predicate(value: Any, sink: list[PredicateResult]) -> Any:
    """Capture a PredicateResult (if present) while preserving expression semantics."""

    if isinstance(value, PredicateResult):
        sink.append(value)
    return value


def __merit_capture_metric_attr(obj: Any, attr: str, sink: list["MetricResult"]) -> Any:
    """Capture metric attribute reads on Metric instances while preserving semantics.

    We record only "numeric-like" values (int/float/bool) or lists/tuples of those
    to keep MetricResult stable and JSON-serializable.
    """

    # Local import to avoid import cycles during package initialization.
    from merit.metrics.base import Metric  # noqa: PLC0415
    from merit.metrics.result import MetricResult  # noqa: PLC0415

    val = getattr(obj, attr)
    if not isinstance(obj, Metric):
        return val

    metric_name = obj.name or type(obj).__name__

    match val:
        case int() | float() | bool():
            sink.append(
                MetricResult(
                    metric_full_name=f"{metric_name}.{attr}",
                    metric_value=float(val),
                )
            )
        case list() | tuple() if all(isinstance(v, (int, float, bool)) for v in val):
            sink.append(
                MetricResult(
                    metric_full_name=f"{metric_name}.{attr}",
                    metric_value=[float(v) for v in val],
                )
            )
        case _:
            pass

    return val


def build_injected_globals() -> dict[str, Any]:
    """Build the globals mapping injected into rewritten modules.

    Why: compiled transformed code references these names directly (e.g. `AssertionResult`,
    `__merit_record_assertion_result`), so they must exist in the module's globals.
    """

    # Local imports to avoid import cycles during package initialization.
    from merit.metrics.base import Metric  # noqa: PLC0415
    from merit.metrics.result import MetricResult  # noqa: PLC0415

    return {
            # Context vars (also useful to users/tests if they reference them directly)
            "TEST_CONTEXT": TEST_CONTEXT,
            "METRICS_CONTEXT": METRICS_CONTEXT,
            # Runtime helper callables
            "__merit_record_assertion_result": __merit_record_assertion_result,
            "__merit_capture_predicate": __merit_capture_predicate,
            "__merit_capture_metric_attr": __merit_capture_metric_attr,
            # Types / containers used by transformed code or helper implementations
            "AssertionResult": AssertionResult,
            "PredicateResult": PredicateResult,
            "Metric": Metric,
            "MetricResult": MetricResult,
        }


class AssertExprRewriter:
    """Expression rewriter used inside a single `assert` condition."""

    def __init__(self, predicate_sink_name: str, metric_sink_name: str) -> None:
        self._predicate_sink_name = predicate_sink_name
        self._metric_sink_name = metric_sink_name

    def rewrite(self, node: ast.expr, *, in_await: bool = False) -> ast.expr:
        """Rewrite an expression tree for captures."""

        match node:
            case ast.Await(value=value):
                if isinstance(value, ast.Call):
                    rewritten_call = self._rewrite_call(value, wrap_predicate=False)
                    awaited = ast.Await(value=rewritten_call)
                    return self._wrap_capture_predicate(awaited)

                return ast.Await(value=self.rewrite(value, in_await=True))

            case ast.Call():
                return self._rewrite_call(node, wrap_predicate=not in_await)

            case ast.Attribute(value=value, attr=attr, ctx=ast.Load()):
                rewritten_obj = self.rewrite(value, in_await=in_await)
                call = ast.Call(
                    func=ast.Name(id="__merit_capture_metric_attr", ctx=ast.Load()),
                    args=[
                        rewritten_obj,
                        ast.Constant(attr),
                        ast.Name(id=self._metric_sink_name, ctx=ast.Load()),
                    ],
                    keywords=[],
                )
                return ast.copy_location(call, node)

            case _:
                # Generic recursive rewrite for all other expression nodes.
                for field, old_value in ast.iter_fields(node):
                    if isinstance(old_value, list):
                        new_list: list[Any] = []
                        changed = False
                        for item in old_value:
                            if isinstance(item, ast.expr):
                                rewritten = self.rewrite(item, in_await=in_await)
                                new_list.append(rewritten)
                                changed = changed or (rewritten is not item)
                            else:
                                new_list.append(item)
                        if changed:
                            setattr(node, field, new_list)
                    elif isinstance(old_value, ast.expr):
                        rewritten = self.rewrite(old_value, in_await=in_await)
                        if rewritten is not old_value:
                            setattr(node, field, rewritten)
                return node

    def _rewrite_call(self, node: ast.Call, *, wrap_predicate: bool) -> ast.expr:
        # Rewrite children first (including attribute access on the callee).
        func = self.rewrite(node.func)
        args = [self.rewrite(a) for a in node.args]
        keywords = [
            ast.keyword(arg=kw.arg, value=self.rewrite(kw.value)) for kw in node.keywords
        ]
        rebuilt = ast.Call(func=func, args=args, keywords=keywords)
        rebuilt = ast.copy_location(rebuilt, node)
        if not wrap_predicate:
            return rebuilt
        return self._wrap_capture_predicate(rebuilt)

    def _wrap_capture_predicate(self, inner: ast.expr) -> ast.expr:
        call = ast.Call(
            func=ast.Name(id="__merit_capture_predicate", ctx=ast.Load()),
            args=[inner, ast.Name(id=self._predicate_sink_name, ctx=ast.Load())],
            keywords=[],
        )
        return ast.copy_location(call, inner)


class AssertRewriteTransformer(ast.NodeTransformer):
    """Rewrite `assert` statements to record `AssertionResult` instead of raising."""

    def __init__(self, source: str, *, filename: str) -> None:
        self._source = source
        self._filename = filename

    def visit_Assert(self, node: ast.Assert) -> list[ast.stmt]:  # noqa: N802 - ast API
        pred_sink = "__merit_predicate_results"
        metric_sink = "__merit_metric_results"
        passed_name = "__merit_passed"
        msg_name = "__merit_error_message"
        ar_name = "__merit_ar"

        expr_text = ast.get_source_segment(self._source, node.test)
        if expr_text is None:
            try:
                expr_text = ast.unparse(node.test)
            except Exception:
                expr_text = "<assertion>"

        expr_rewriter = AssertExprRewriter(predicate_sink_name=pred_sink, metric_sink_name=metric_sink)
        rewritten_test = expr_rewriter.rewrite(ast.fix_missing_locations(ast.copy_location(node.test, node.test)))

        # Build statement block.
        pred_init = ast.Assign(
            targets=[ast.Name(id=pred_sink, ctx=ast.Store())],
            value=ast.List(elts=[], ctx=ast.Load()),
        )
        metric_init = ast.Assign(
            targets=[ast.Name(id=metric_sink, ctx=ast.Store())],
            value=ast.List(elts=[], ctx=ast.Load()),
        )

        passed_assign = ast.Assign(
            targets=[ast.Name(id=passed_name, ctx=ast.Store())],
            value=ast.Call(func=ast.Name(id="bool", ctx=ast.Load()), args=[rewritten_test], keywords=[]),
        )

        if node.msg is None:
            msg_assign = ast.Assign(
                targets=[ast.Name(id=msg_name, ctx=ast.Store())],
                value=ast.Constant(None),
            )
        else:
            # Preserve assert-message laziness: evaluate msg only when failing.
            msg_assign = ast.If(
                test=ast.UnaryOp(op=ast.Not(), operand=ast.Name(id=passed_name, ctx=ast.Load())),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=msg_name, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id="str", ctx=ast.Load()),
                            args=[expr_rewriter.rewrite(node.msg)],
                            keywords=[],
                        ),
                    )
                ],
                orelse=[
                    ast.Assign(
                        targets=[ast.Name(id=msg_name, ctx=ast.Store())],
                        value=ast.Constant(None),
                    )
                ],
            )

        ar_assign = ast.Assign(
            targets=[ast.Name(id=ar_name, ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id="AssertionResult", ctx=ast.Load()),
                args=[],
                keywords=[
                    ast.keyword(arg="expression", value=ast.Constant(expr_text)),
                    ast.keyword(arg="passed", value=ast.Name(id=passed_name, ctx=ast.Load())),
                    ast.keyword(arg="error_message", value=ast.Name(id=msg_name, ctx=ast.Load())),
                ],
            ),
        )

        extend_predicates = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(value=ast.Name(id=ar_name, ctx=ast.Load()), attr="captured_predicate_results", ctx=ast.Load()),
                    attr="extend",
                    ctx=ast.Load(),
                ),
                args=[ast.Name(id=pred_sink, ctx=ast.Load())],
                keywords=[],
            )
        )
        extend_metrics = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(value=ast.Name(id=ar_name, ctx=ast.Load()), attr="captured_metric_results", ctx=ast.Load()),
                    attr="extend",
                    ctx=ast.Load(),
                ),
                args=[ast.Name(id=metric_sink, ctx=ast.Load())],
                keywords=[],
            )
        )

        record_call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="__merit_record_assertion_result", ctx=ast.Load()),
                args=[ast.Name(id=ar_name, ctx=ast.Load())],
                keywords=[],
            )
        )

        block: list[ast.stmt] = [
            pred_init,
            metric_init,
            passed_assign,
            msg_assign,
            ar_assign,
            extend_predicates,
            extend_metrics,
            record_call,
        ]

        # Preserve useful locations for debugging.
        for stmt in block:
            ast.copy_location(stmt, node)

        return block