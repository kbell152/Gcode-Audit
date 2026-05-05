# Tests

Test suite for the G-Code Audit Engine. Uses [pytest](https://docs.pytest.org/).

## Running the tests

From the repo root, with your venv activated:

```bash
# Run everything
pytest

# Run a single file
pytest tests/test_g91.py

# Run tests whose name matches a substring
pytest -k spindle
pytest -k g91

# Run a specific test
pytest tests/test_validators.py::TestSpindleAndFeed::test_cut_with_spindle_off_flagged_critical

# More verbose output (full assertion details)
pytest -vv

# Stop at first failure
pytest -x

# Show what's slow
pytest --durations=10
```

When tests pass you'll see something like:

```
tests/test_g91.py::test_g90_absolute_mode_replaces_position PASSED
tests/test_g91.py::test_g91_increments_from_prior_position PASSED
...
======================== 80 passed in 0.12s ========================
```

When tests fail, pytest shows the assertion that failed, with the
actual vs. expected values inlined. No need to add print statements —
pytest handles the diagnostics.

## Test files

| File                  | Covers                                              |
|-----------------------|-----------------------------------------------------|
| `test_parser.py`      | Tokenizer, comment stripping, line classification, modal state, output shape, defensive input validation |
| `test_g91.py`         | G91 incremental coordinate interpretation (v4)      |
| `test_validators.py`  | All four validators with positive AND negative cases |
| `test_regression.py`  | Locks in expected output for the real-world `tests/gcode/test.gcode` |
| `conftest.py`         | Sets up import path so tests can find `src/` (do not edit unless restructuring) |

## How tests are organized

Two patterns coexist in this suite:

**Plain function tests** (used in `test_g91.py`) — each test is a
top-level function whose name starts with `test_`. Pytest finds and
runs them automatically.

```python
def test_my_thing():
    result = do_something()
    assert result == 42
```

**Class-grouped tests** (used in `test_parser.py`, `test_validators.py`,
`test_regression.py`) — related tests grouped under a class whose name
starts with `Test`. Useful when several tests share a topic or setup.
The class is just a namespace; no special methods are required.

```python
class TestMyTopic:
    def test_one_thing(self):
        ...
    def test_another_thing(self):
        ...
```

Either pattern works. Use whichever reads better for the test you're
writing. Class grouping helps when you have 5+ related tests and don't
want them to blur together with everything else in the file.

## Adding a new test

The general loop:

1. Decide what behavior you want to lock in
2. Write a test that would fail if that behavior broke
3. Run `pytest` and confirm the test PASSES against the current code
4. Make your change to the engine
5. Run `pytest` again and confirm:
   - All previously-passing tests still pass (no regression)
   - Any new tests covering your change pass

If a test you're writing only passes after your code change, that's
exactly what you want — it proves the test catches the thing it's
supposed to catch.

### Where to add tests

| What you're testing | Add it to |
|---------------------|-----------|
| New tokenizer / parser behavior | `test_parser.py` |
| New validator | New file `test_<validator_name>.py`, or extend `test_validators.py` |
| New parser-level issue type | `test_parser.py` (or its own file if substantial) |
| Behavior that should match an expected output for a real-world G-code file | `test_regression.py` |

### A good test has

- **A descriptive name** — `test_g91_increments_from_prior_position` is
  good; `test_g91` is not. The name should tell you what the test
  expects without reading the body.
- **A docstring** — one sentence explaining what behavior is being
  locked in. Useful when a test fails and you're trying to remember
  why it exists.
- **One thing it's checking** — a test that asserts ten unrelated
  things gives a confusing failure message. Split unrelated assertions
  into separate tests.
- **Both positive and negative coverage where it matters** — for
  validators, test that they DO flag bad programs AND don't flag good
  ones.

## Updating regression tests

If you deliberately change behavior that `test_regression.py` checks
(e.g. you add a new issue type that fires on `test.gcode`), the
regression test will fail. That's correct — it's flagging the change.

When that happens:

1. Look at the failure carefully and confirm the new behavior is
   actually what you intended
2. Update the expected values in `test_regression.py` to match
3. Mention the regression-test update in the changelog so future you
   knows why the expected values changed

Don't update regression expected values without checking. The whole
point of the test is that drift forces a conscious review.

## Working with the venv

All test commands assume your venv is activated:

```bash
source .venv/bin/activate
```

If you see `ModuleNotFoundError: No module named 'pytest'`, your venv
isn't activated (or pytest isn't installed in it — run
`pip install -r requirements-dev.txt`).
