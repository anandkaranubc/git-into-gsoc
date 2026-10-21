# Sparse polynomial GCD for SymPy

## Synopsis

`sympy/polys/sqfreetools.py` and `densetools.py` implement GCD for the dense
representation only. This project adds a sparse multivariate GCD (`sparse_gcd()`)
in `sympy/polys/ring_series.py`, building on #27019 and the discussion in
https://github.com/sympy/sympy/issues/27019.

## Benefits to the community

Users of `Poly.gcd()` with many variables see 10x speedups (see the benchmark in PR
https://github.com/sympy/sympy/pull/28100).

## Deliverables

1. `sparse_gcd()` with tests in `sympy/polys/tests/test_sparse_gcd.py`
2. Documentation page under `doc/src/modules/polys/`

## Timeline

Week 1: read `heuristicgcd()` and write failing tests.
Week 2: implement univariate case.
Week 3: multivariate case.
Week 4: buffer week for review feedback.
Week 5: benchmarks.
Week 6: docs.
Week 7: integrate with `Poly.gcd()`.
Week 8: final cleanup and buffer.

## Prior contributions

- https://github.com/sympy/sympy/pull/28100 (merged)
- https://github.com/sympy/sympy/pull/28150

## About me

Second-year student; I maintain a small CAS in Rust.

## Availability

30 hours per week from June to August, no other commitments.

## AI usage

I used an assistant to draft test scaffolding and reviewed every line.
