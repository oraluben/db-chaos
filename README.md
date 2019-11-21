# Chaos Testing Framework (for Database)

## A Kubernetes-based demo

## Files and Directory

### `poc`
1. (POC) Deploy database cluster with Kubernetes
2. Docker image for further framework

### `tidb-bench`
Benchmark from `git@github.com:pingcap/tidb-bench.git`, you may need to update git submodules

### `test_template`
Test framework, demo are `ssb.py` and `ssb-chaos.py`

### `ssb.py`
Star Schema Benchmark from `tidb-bench`

### `ssb-chaos.py`
ssb test as above, with chaos testing

## Test Framework

### Abstractions

All symbols under this section are defined in `test_template` package

#### `Node`
Abstraction of node when testing, including Docker image and custom initialization.
Some predefined nodes are in `nodes`

#### `TestBed`
Abstraction of test environment, including `Node` configs and initialization.

#### `Test`
Abstraction of one test, including corresponding `TestBed` and test logic.

#### `TestAction`
Abstraction of test behavior, some predefined actions are in `actions`.

#### `chaos.ChaosOperator`
"Operator" for chaos testing

#### `chaos.ChaosAction`
`TestAction` to enable or disable `ChaosOperator`

#### `chaos.Manager`
Manage random chaos behavior during test.

## Dependence
1. Python3 with `kubernetes` package
2. `CopyBuildSsb` requires `kubectl cp` to work

## Run
* `cd <repo-dir>` to use `test_template` package

Run original test without chaos: `$ python3 ssb.py`
Run original test without chaos: `$ python3 ssb-chaos.py`