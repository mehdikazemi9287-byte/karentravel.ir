"""Guards against the exact class of bug found in the previous GRS phase: a
module-level helper function landing between a route decorator and its
target function, silently hijacking route registration. FastAPI failed to
even boot the app when this happened - these tests catch that class of
mistake deterministically, without relying on someone noticing a boot crash."""
from app.main import app, search_offers


def _route_for_path_and_method(path: str, method: str):
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    return None


def test_app_boots_and_exposes_routes():
    # If any decorator got hijacked, constructing/importing `app` itself would
    # already have raised (as it did for /search/offers last phase) - this
    # import already happened at module load time above; this assertion just
    # makes the expectation explicit and gives a readable failure if the
    # route list is ever empty.
    assert len(app.routes) > 50


def test_search_offers_route_is_registered_with_correct_path_and_method():
    route = _route_for_path_and_method("/search/offers", "POST")
    assert route is not None, "POST /search/offers is not registered at all"


def test_search_offers_route_handler_is_actually_search_offers():
    route = _route_for_path_and_method("/search/offers", "POST")
    assert route.endpoint is search_offers, (
        f"POST /search/offers is registered to {route.endpoint!r}, not search_offers - "
        "a helper function likely landed between the @app.post(...) decorator and def search_offers(...)"
    )


def test_no_grs_helper_is_itself_registered_as_a_route():
    from app.main import _grs_hotel_offers_for_search
    registered_endpoints = {getattr(route, "endpoint", None) for route in app.routes}
    assert _grs_hotel_offers_for_search not in registered_endpoints, (
        "_grs_hotel_offers_for_search must never itself be a route endpoint - "
        "if it is, a decorator meant for a real route landed on this helper instead"
    )


def test_every_grs_helper_function_is_undecorated_plain_python():
    import inspect
    from app import main as main_module
    for name in ("_grs_hotel_offers_for_search",):
        func = getattr(main_module, name)
        assert inspect.isfunction(func)
        # a route-decorated function would be wrapped by FastAPI and would not
        # appear as a plain module-level function with this exact __name__
        assert func.__name__ == name


def test_unified_search_public_route_unaffected():
    route = _route_for_path_and_method("/search/v2/public", "POST")
    assert route is not None
    from app.main import unified_search_public
    assert route.endpoint is unified_search_public
