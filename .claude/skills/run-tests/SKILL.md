---
name: run-tests
description: Run the HermesHQ backend pytest suite with the correct CI exclusions. Use when you want to verify backend changes haven't broken anything.
disable-model-invocation: true
---

Run the HermesHQ backend test suite on the Mac Mini host.

The following test files are always excluded — they contain known failures or require special infrastructure not available in CI:
- `tests/test_gateway_supervisor_crash_loop.py`
- `tests/test_regressions.py`
- `tests/test_response_attachments.py`

Tell the user to run on the Mac Mini host:

```bash
cd backend
python -m pytest tests/ -v --tb=short \
  --ignore=tests/test_gateway_supervisor_crash_loop.py \
  --ignore=tests/test_regressions.py \
  --ignore=tests/test_response_attachments.py
```

To run a single test by name:
```bash
python -m pytest tests/ -v --tb=short -k "test_name_here" \
  --ignore=tests/test_gateway_supervisor_crash_loop.py \
  --ignore=tests/test_regressions.py \
  --ignore=tests/test_response_attachments.py
```

Note: `asyncio_mode = auto` is configured in `pytest.ini` — no `@pytest.mark.asyncio` decorator needed.
