"""One module per domain, written asynchronously. ``resources_sync/`` is generated from here.

Nothing is re-exported: a resource is reached through the client (``pv.publications``), never
imported by hand, so a name here is an implementation detail and moving one is not a breaking
change.
"""
