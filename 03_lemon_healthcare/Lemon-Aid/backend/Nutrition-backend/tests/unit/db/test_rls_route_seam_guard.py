"""Regression guard: every owner route must sit on an RLS seam before the flip.

After the FORCE RLS Stage-2 flip ``DATABASE_URL`` connects as the non-superuser
``lemon_app`` role. A route on the plain ``get_async_session`` dependency sets no
per-request RLS GUCs and commits owner/audit writes in-session, so under the flip
it silently fails closed (owner reads return 0 rows; ``audit_logs`` INSERT is
denied → 500). Owner routes must therefore either:

* use ``get_rls_context_session`` (dependency opens the request tx + sets GUCs), or
* keep ``get_async_session`` **and** wrap their body in
  ``rls_request_transaction`` / ``rls_request_transaction_allow_inner_commit``
  (needed only when the route schedules post-commit BackgroundTasks or calls a
  DO-NOT-TOUCH callee that commits + refreshes mid-request).

This test fails if any *new* route adopts ``get_async_session`` without being
added to the in-body-CM allowlist below — catching the exact class of bug that
left four supplement CRUD routes unmigrated until the live flip exposed them.
"""

from __future__ import annotations

import inspect

from fastapi.dependencies.utils import get_flat_dependant
from fastapi.routing import APIRoute
from src.db.dependencies import get_async_session, get_rls_context_session
from src.main import create_app


def _is_dependency(call: object, reference: object) -> bool:
    """Match a route dependency to a reference callable by stable name coordinates.

    ``is`` identity is fragile under CI import layouts where the same module can be
    imported under two sys.path roots (e.g. ``src.db.dependencies`` resolved twice),
    yielding distinct function objects for identical source — which silently makes
    every route look like it dropped the dependency. Comparing ``__qualname__`` plus
    the module tail is identity-immune without weakening the guard.
    """
    if call is reference:
        return True
    module_tail = ".".join(reference.__module__.rsplit(".", 2)[-2:])
    return getattr(call, "__qualname__", None) == reference.__qualname__ and (
        getattr(call, "__module__", "") or ""
    ).endswith(module_tail)


# Routes that intentionally keep ``get_async_session`` because they own their RLS
# transaction *in the route body* (rls_request_transaction /
# rls_request_transaction_allow_inner_commit). Adding a route here is a conscious
# assertion that its body is CM-wrapped. Anything else on get_async_session is a bug.
_IN_BODY_RLS_CM_ROUTES: frozenset[str] = frozenset(
    {
        "run_chatbot",  # rls_request_transaction_allow_inner_commit (store inner commit+refresh)
        "analyze_supplement_label",  # rls_request_transaction (+ post-commit learning task)
        "upload_supplement_analysis_session_image",  # rls_request_transaction
        "analyze_supplement_label_multi",  # rls_request_transaction
        "create_user_supplement",  # rls_request_transaction (+ post-commit learning task)
    }
)


# Owner routes that were unmigrated until the live flip exposed them (HTTP 500:
# GUC-less owner reads returned 0 rows; in-session audit INSERT denied). They must
# stay on get_rls_context_session so reads carry the per-request GUC and audits go
# out-of-band on the privileged engine.
_RLS_DEP_REQUIRED_ROUTES: frozenset[str] = frozenset(
    {
        "list_user_supplements",
        "get_user_supplement",
        "delete_user_supplement",
        "explain_supplement_recommendations",
    }
)


def _route_deps_by_endpoint_name() -> dict[str, set[object]]:
    """Map each route's endpoint name to the set of dependency callables it uses."""
    app = create_app()
    deps: dict[str, set[object]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        flat = get_flat_dependant(route.dependant)
        deps[route.endpoint.__name__] = {dep.call for dep in flat.dependencies}
    return deps


def _routes_using_get_async_session() -> list[str]:
    """Return ``"NAME (METHODS PATH)"`` for every route depending on get_async_session."""
    app = create_app()
    offenders: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        flat = get_flat_dependant(route.dependant)
        if any(_is_dependency(dep.call, get_async_session) for dep in flat.dependencies):
            methods = ",".join(sorted(route.methods or set()))
            offenders.append(f"{route.endpoint.__name__} ({methods} {route.path})")
    return offenders


def test_no_route_uses_get_async_session_outside_the_cm_wrapped_allowlist() -> None:
    """Any get_async_session route not in the in-body-CM allowlist is flip-unsafe."""
    using = _routes_using_get_async_session()
    offenders = sorted(
        entry for entry in using if entry.split(" ", 1)[0] not in _IN_BODY_RLS_CM_ROUTES
    )
    assert not offenders, (
        "These routes depend on get_async_session but are not in the in-body-RLS-CM "
        "allowlist; under the lemon_app FORCE-RLS flip their owner reads return 0 rows "
        "and in-session audit/owner writes fail closed. Migrate to "
        "get_rls_context_session, or wrap the body in rls_request_transaction* and add "
        "the route to _IN_BODY_RLS_CM_ROUTES: " + "; ".join(offenders)
    )


def test_cm_wrapped_allowlist_has_no_stale_entries() -> None:
    """Every allowlisted name must still be a live get_async_session route."""
    live = {entry.split(" ", 1)[0] for entry in _routes_using_get_async_session()}
    stale = sorted(_IN_BODY_RLS_CM_ROUTES - live)
    assert not stale, (
        "These allowlist entries no longer use get_async_session (route renamed, "
        "removed, or migrated to get_rls_context_session); drop them from "
        "_IN_BODY_RLS_CM_ROUTES: " + ", ".join(stale)
    )


def test_formerly_unmigrated_supplement_routes_sit_on_get_rls_context_session() -> None:
    """Lock in the fix: the four flip-exposed owner routes must use the RLS dep."""
    deps = _route_deps_by_endpoint_name()
    missing = sorted(
        name
        for name in _RLS_DEP_REQUIRED_ROUTES
        if not any(_is_dependency(dep, get_rls_context_session) for dep in deps.get(name, set()))
    )
    assert not missing, (
        "These owner routes must depend on get_rls_context_session (per-request GUC + "
        "out-of-band audit) or they fail closed under the lemon_app FORCE-RLS flip: "
        + ", ".join(missing)
    )


def _endpoint_by_name() -> dict[str, object]:
    """Map each route's endpoint name to its (unwrapped) endpoint callable."""
    app = create_app()
    endpoints: dict[str, object] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoints[route.endpoint.__name__] = inspect.unwrap(route.endpoint)
    return endpoints


def test_in_body_cm_routes_actually_wrap_their_body() -> None:
    """Allowlisted routes must really reference an RLS CM in their body, not just claim it.

    ``_IN_BODY_RLS_CM_ROUTES`` is a human assertion that a ``get_async_session`` route
    wraps its body in ``rls_request_transaction`` / ``rls_request_transaction_allow_inner_commit``.
    Without this check, refactoring the wrapper out of an allowlisted route would still
    pass the guard (false negative) and ship a flip-unsafe route. Assert the source of
    each allowlisted endpoint references the CM (the substring also covers the
    ``_allow_inner_commit`` variant).
    """
    endpoints = _endpoint_by_name()
    missing = sorted(
        name
        for name in _IN_BODY_RLS_CM_ROUTES
        if name in endpoints and "rls_request_transaction" not in inspect.getsource(endpoints[name])
    )
    assert not missing, (
        "These allowlisted routes no longer reference an RLS context manager in their "
        "body (rls_request_transaction*), so they are flip-unsafe despite being "
        "allowlisted; restore the wrapper or migrate to get_rls_context_session: "
        + ", ".join(missing)
    )
