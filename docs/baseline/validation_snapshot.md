# Baseline Validation Snapshot

Date: 2026-03-16T10:20:40Z

## Convergence Validation Script
poetry not found; skipping ruff/mypy checks in local validation script
OpenAPI snapshot check passed
...................................................                      [100%]
51 passed in 4.21s
....                                                                     [100%]
=============================== warnings summary ===============================
tests/contracts/test_api_contracts.py::test_required_dashboard_paths_and_methods_present
  /Users/parthdama/Documents/Nexra/nexra/api/main.py:97: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("shutdown")

tests/contracts/test_api_contracts.py::test_required_dashboard_paths_and_methods_present
  /Users/parthdama/Documents/Nexra/nexra/venv/lib/python3.12/site-packages/fastapi/applications.py:4495: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
4 passed, 2 warnings in 2.89s

> nexra-dashboard@0.0.0 build
> tsc -b && vite build

vite v6.4.1 building for production...
transforming...
✓ 759 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                             0.47 kB │ gzip:   0.30 kB
dist/assets/index-CIrw-mkW.css              8.82 kB │ gzip:   2.35 kB
dist/assets/formatters-CRQ5zJIT.js          0.73 kB │ gzip:   0.41 kB │ map:     3.80 kB
dist/assets/StatusPill-WUBonxbF.js          1.20 kB │ gzip:   0.45 kB │ map:     2.79 kB
dist/assets/PolicyEngine-DKW0bXy3.js        2.13 kB │ gzip:   0.97 kB │ map:     4.89 kB
dist/assets/EmptyState-DA1nTZwG.js          2.58 kB │ gzip:   1.12 kB │ map:     8.34 kB
dist/assets/useMutation-DP6YFonD.js         3.15 kB │ gzip:   1.31 kB │ map:     9.65 kB
dist/assets/TrustScores-CEkaM4vb.js         3.35 kB │ gzip:   1.35 kB │ map:     7.67 kB
dist/assets/AgentRegistry-cWJJOt6_.js       3.57 kB │ gzip:   1.40 kB │ map:     8.93 kB
dist/assets/DelegationFeed-C4U-DMnx.js      3.72 kB │ gzip:   1.41 kB │ map:     9.47 kB
dist/assets/ComplianceExport-gBHgG7Cd.js    3.85 kB │ gzip:   1.69 kB │ map:    10.49 kB
dist/assets/HitlQueue-DzJNyyzI.js           4.10 kB │ gzip:   1.51 kB │ map:    10.22 kB
dist/assets/PolicyDetail-B097qtzU.js        4.21 kB │ gzip:   1.48 kB │ map:    11.24 kB
dist/assets/Anomalies-D5iqfPI-.js           4.46 kB │ gzip:   1.32 kB │ map:    10.40 kB
dist/assets/DelegationDetail-C3EwhnpJ.js    5.03 kB │ gzip:   1.68 kB │ map:    12.42 kB
dist/assets/AuditLog-BYmS8mce.js            5.11 kB │ gzip:   2.02 kB │ map:    13.23 kB
dist/assets/SpendBudget-hUyAmhEH.js         5.76 kB │ gzip:   2.05 kB │ map:    15.66 kB
dist/assets/Settings-B9IoMiIW.js            5.77 kB │ gzip:   1.91 kB │ map:    15.31 kB
dist/assets/Overview-CBLvERoz.js            6.28 kB │ gzip:   2.10 kB │ map:    16.72 kB
dist/assets/AgentDetail-D95NY4Eb.js         7.69 kB │ gzip:   2.35 kB │ map:    19.95 kB
dist/assets/useQuery-CMdczVsP.js           10.47 kB │ gzip:   3.75 kB │ map:    41.07 kB
dist/assets/index-D_qEOmcW.js             269.46 kB │ gzip:  85.40 kB │ map: 1,458.67 kB
dist/assets/LineChart-B_-jdrJZ.js         346.01 kB │ gzip: 103.58 kB │ map: 1,799.92 kB
✓ built in 8.60s

> @nexra/sdk@0.1.0 build
> tsc

Convergence validation checks passed

## Python Integration + E2E Tests (sandbox expectation)
EEEEEEEEEEEEEEEEEEEEEEEE                                                 [100%]
==================================== ERRORS ====================================
_____ ERROR at setup of TestAuditLogAppend.test_append_creates_audit_entry _____

request = <SubRequest 'db_session' for <Coroutine test_append_creates_audit_entry>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10e86cc20>
setup_task = <Task finished name='Task-1' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, de...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
___ ERROR at setup of TestAuditLogAppend.test_query_returns_own_org_entries ____

request = <SubRequest 'db_session' for <Coroutine test_query_returns_own_org_entries>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10e86c040>
setup_task = <Task finished name='Task-5' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, de...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_____ ERROR at setup of TestAuditLogAppend.test_query_filter_by_event_type _____

request = <SubRequest 'db_session' for <Coroutine test_query_filter_by_event_type>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10e9c2660>
setup_task = <Task finished name='Task-9' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, de...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
______ ERROR at setup of TestAuditLogAppend.test_query_filter_by_agent_id ______

request = <SubRequest 'db_session' for <Coroutine test_query_filter_by_agent_id>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa0a2a0>
setup_task = <Task finished name='Task-13' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_____________ ERROR at setup of TestAuditLogAppend.test_csv_export _____________

request = <SubRequest 'db_session' for <Coroutine test_csv_export>>, kwargs = {}
func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa0b1a0>
setup_task = <Task finished name='Task-17' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_ ERROR at setup of TestAuditLogImmutability.test_update_is_rejected_by_trigger _

request = <SubRequest 'db_session' for <Coroutine test_update_is_rejected_by_trigger>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa0b880>
setup_task = <Task finished name='Task-21' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_ ERROR at setup of TestAuditLogImmutability.test_delete_is_rejected_by_trigger _

request = <SubRequest 'db_session' for <Coroutine test_delete_is_rejected_by_trigger>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa0bc40>
setup_task = <Task finished name='Task-25' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_ ERROR at setup of TestDelegationPolicyBlocking.test_no_policies_blocks_delegation _

request = <SubRequest 'db_session' for <Coroutine test_no_policies_blocks_delegation>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa0ade0>
setup_task = <Task finished name='Task-29' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_ ERROR at setup of TestDelegationWithPolicy.test_policy_allows_creates_delegation_record _

request = <SubRequest 'db_session' for <Coroutine test_policy_allows_creates_delegation_record>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa08720>
setup_task = <Task finished name='Task-33' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
__ ERROR at setup of TestDelegationHiTL.test_hil_threshold_pauses_delegation ___

request = <SubRequest 'db_session' for <Coroutine test_hil_threshold_pauses_delegation>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10e9c34c0>
setup_task = <Task finished name='Task-37' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_ ERROR at setup of TestDelegationDepth.test_parent_delegation_increments_depth _

request = <SubRequest 'db_session' for <Coroutine test_parent_delegation_increments_depth>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10e95f2e0>
setup_task = <Task finished name='Task-41' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
___ ERROR at setup of TestDiscovery.test_discover_returns_registered_agents ____

request = <SubRequest 'db_session' for <Coroutine test_discover_returns_registered_agents>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa0a520>
setup_task = <Task finished name='Task-45' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
______ ERROR at setup of TestDiscovery.test_discover_excludes_quarantined ______

request = <SubRequest 'db_session' for <Coroutine test_discover_excludes_quarantined>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10eea2a20>
setup_task = <Task finished name='Task-49' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
___ ERROR at setup of TestDiscovery.test_discover_filters_by_capability_type ___

request = <SubRequest 'db_session' for <Coroutine test_discover_filters_by_capability_type>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10eea2020>
setup_task = <Task finished name='Task-53' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_________ ERROR at setup of TestDiscovery.test_discover_exclude_agents _________

request = <SubRequest 'db_session' for <Coroutine test_discover_exclude_agents>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10eea14e0>
setup_task = <Task finished name='Task-57' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
___ ERROR at setup of TestDiscovery.test_discover_composite_score_structure ____

request = <SubRequest 'db_session' for <Coroutine test_discover_composite_score_structure>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10e95f2e0>
setup_task = <Task finished name='Task-61' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_______ ERROR at setup of TestAgentRegistration.test_register_new_agent ________

request = <SubRequest 'db_session' for <Coroutine test_register_new_agent>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10e9c22a0>
setup_task = <Task finished name='Task-65' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_ ERROR at setup of TestAgentRegistration.test_register_idempotent_on_agent_id _

request = <SubRequest 'db_session' for <Coroutine test_register_idempotent_on_agent_id>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10eea2700>
setup_task = <Task finished name='Task-69' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_ ERROR at setup of TestAgentRegistration.test_list_agents_returns_registered __

request = <SubRequest 'db_session' for <Coroutine test_list_agents_returns_registered>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10eea3920>
setup_task = <Task finished name='Task-73' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_________ ERROR at setup of TestAgentRegistration.test_get_by_agent_id _________

request = <SubRequest 'db_session' for <Coroutine test_get_by_agent_id>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10eea28e0>
setup_task = <Task finished name='Task-77' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
________ ERROR at setup of TestAgentRegistration.test_quarantine_agent _________

request = <SubRequest 'db_session' for <Coroutine test_quarantine_agent>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa0bb00>
setup_task = <Task finished name='Task-81' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_________ ERROR at setup of TestAgentRegistration.test_activate_agent __________

request = <SubRequest 'db_session' for <Coroutine test_activate_agent>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10fa089a0>
setup_task = <Task finished name='Task-85' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
_ ERROR at setup of TestAgentRegistration.test_different_orgs_can_have_same_agent_id _

request = <SubRequest 'db_session' for <Coroutine test_different_orgs_can_have_same_agent_id>>
kwargs = {}, func = <function db_session at 0x1095f0400>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10f7c7600>
setup_task = <Task finished name='Task-89' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/conftest.py:30: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
___ ERROR at setup of TestFullDelegationFlow.test_full_delegation_roundtrip ____

request = <SubRequest 'db_session' for <Coroutine test_full_delegation_roundtrip>>
kwargs = {}, func = <function db_session at 0x10a0bd1c0>
event_loop_fixture_id = 'event_loop'
setup = <function _wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup at 0x10e95efc0>
setup_task = <Task finished name='Task-93' coro=<_wrap_asyncgen_fixture.<locals>._asyncgen_fixture_wrapper.<locals>.setup() done, d...env/lib/python3.12/site-packages/pytest_asyncio/plugin.py:339> exception=PermissionError(1, 'Operation not permitted')>

    @functools.wraps(fixture)
    def _asyncgen_fixture_wrapper(request: FixtureRequest, **kwargs: Any):
        func = _perhaps_rebind_fixture_func(fixture, request.instance)
        event_loop_fixture_id = _get_event_loop_fixture_id_for_async_fixture(
            request, func
        )
        event_loop = request.getfixturevalue(event_loop_fixture_id)
        kwargs.pop(event_loop_fixture_id, None)
        gen_obj = func(**_add_kwargs(func, kwargs, event_loop, request))
    
        async def setup():
            res = await gen_obj.__anext__()  # type: ignore[union-attr]
            return res
    
        context = contextvars.copy_context()
        setup_task = _create_task_in_context(event_loop, setup(), context)
>       result = event_loop.run_until_complete(setup_task)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:345: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:687: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py:340: in setup
    res = await gen_obj.__anext__()  # type: ignore[union-attr]
          ^^^^^^^^^^^^^^^^^^^^^^^^^
tests/e2e/conftest.py:21: in db_session
    async with engine.begin() as conn:
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/contextlib.py:210: in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:1068: in begin
    async with conn:
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/base.py:121: in __aenter__
    return await self.start(is_ctxmanager=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/ext/asyncio/engine.py:275: in start
    await greenlet_spawn(self.sync_engine.connect)
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:201: in greenlet_spawn
    result = context.throw(*sys.exc_info())
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:306: in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
    self.__connect()
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
    with util.safe_reraise():
venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
    raise exc_value.with_traceback(exc_tb)
venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
    return dialect.connect(*cargs_tup, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:955: in connect
    await_only(creator_fn(*arg, **kw)),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:132: in await_only
    return current.parent.switch(awaitable)  # type: ignore[no-any-return,attr-defined] # noqa: E501
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connection.py:2421: in connect
    return await connect_utils._connect(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1075: in _connect
    raise last_error or exceptions.TargetServerAttributeNotMatched(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:1049: in _connect
    conn = await _connect_addr(
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:886: in _connect_addr
    return await __connect_addr(params, True, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:931: in __connect_addr
    tr, pr = await connector
             ^^^^^^^^^^^^^^^
venv/lib/python3.12/site-packages/asyncpg/connect_utils.py:802: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1127: in create_connection
    raise exceptions[0]
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1104: in create_connection
    sock = await self._connect_sock(
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py:1007: in _connect_sock
    await self.sock_connect(sock, address)
/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:651: in sock_connect
    return await fut
           ^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <_UnixSelectorEventLoop running=False closed=False debug=False>
fut = None, sock = <socket.socket [closed] fd=-1, family=30, type=1, proto=6>
address = ('::1', 5432, 0, 0)

    def _sock_connect(self, fut, sock, address):
        fd = sock.fileno()
        try:
>           sock.connect(address)
E           PermissionError: [Errno 1] Operation not permitted

/opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/selector_events.py:659: PermissionError
=========================== short test summary info ============================
ERROR tests/integration/test_audit_immutability.py::TestAuditLogAppend::test_append_creates_audit_entry
ERROR tests/integration/test_audit_immutability.py::TestAuditLogAppend::test_query_returns_own_org_entries
ERROR tests/integration/test_audit_immutability.py::TestAuditLogAppend::test_query_filter_by_event_type
ERROR tests/integration/test_audit_immutability.py::TestAuditLogAppend::test_query_filter_by_agent_id
ERROR tests/integration/test_audit_immutability.py::TestAuditLogAppend::test_csv_export
ERROR tests/integration/test_audit_immutability.py::TestAuditLogImmutability::test_update_is_rejected_by_trigger
ERROR tests/integration/test_audit_immutability.py::TestAuditLogImmutability::test_delete_is_rejected_by_trigger
ERROR tests/integration/test_delegation.py::TestDelegationPolicyBlocking::test_no_policies_blocks_delegation
ERROR tests/integration/test_delegation.py::TestDelegationWithPolicy::test_policy_allows_creates_delegation_record
ERROR tests/integration/test_delegation.py::TestDelegationHiTL::test_hil_threshold_pauses_delegation
ERROR tests/integration/test_delegation.py::TestDelegationDepth::test_parent_delegation_increments_depth
ERROR tests/integration/test_discovery.py::TestDiscovery::test_discover_returns_registered_agents
ERROR tests/integration/test_discovery.py::TestDiscovery::test_discover_excludes_quarantined
ERROR tests/integration/test_discovery.py::TestDiscovery::test_discover_filters_by_capability_type
ERROR tests/integration/test_discovery.py::TestDiscovery::test_discover_exclude_agents
ERROR tests/integration/test_discovery.py::TestDiscovery::test_discover_composite_score_structure
ERROR tests/integration/test_registration.py::TestAgentRegistration::test_register_new_agent
ERROR tests/integration/test_registration.py::TestAgentRegistration::test_register_idempotent_on_agent_id
ERROR tests/integration/test_registration.py::TestAgentRegistration::test_list_agents_returns_registered
ERROR tests/integration/test_registration.py::TestAgentRegistration::test_get_by_agent_id
ERROR tests/integration/test_registration.py::TestAgentRegistration::test_quarantine_agent
ERROR tests/integration/test_registration.py::TestAgentRegistration::test_activate_agent
ERROR tests/integration/test_registration.py::TestAgentRegistration::test_different_orgs_can_have_same_agent_id
ERROR tests/e2e/test_full_delegation_flow.py::TestFullDelegationFlow::test_full_delegation_roundtrip
24 errors in 8.48s
