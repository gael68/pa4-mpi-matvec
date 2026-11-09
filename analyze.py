"""Parse PA4 job outputs, print summary tables, and draw the graphs.

usage: python3 analyze.py task2-*.out task4-*.out transpose-*.out
"""
import re
import sys
from collections import defaultdict
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TIME = re.compile(r"Parallel matrix vector multiplication time: ([\d.]+) sec")


def runs(path, header):
    """Map the key captured by header -> list of mvm times that follow it."""
    out = defaultdict(list)
    key = None
    for line in open(path):
        m = header.search(line)
        if m:
            key = int(m.group(1))
        m = TIME.search(line)
        if m and key is not None:
            out[key].append(float(m.group(1)))
    return dict(sorted(out.items()))


def task2(path):
    t = runs(path, re.compile(r"^=== n=(\d+)"))
    print("Task 2: one task")
    print(f"{'n':>6} {'runs':>4} {'avg (s)':>10} {'min (s)':>10} {'avg/n^2 (ns)':>13} {'ratio':>6}")
    prev = None
    for n, v in t.items():
        a = mean(v)
        ratio = f"{a / prev:6.2f}" if prev else ""
        print(f"{n:>6} {len(v):>4} {a:10.6f} {min(v):10.6f} {a / n**2 * 1e9:13.3f} {ratio:>6}")
        prev = a
    ns = list(t)
    avg = [mean(v) for v in t.values()]
    c = avg[-1] / ns[-1] ** 2
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(ns, avg, "o-", label="measured (avg of runs)")
    ax.plot(ns, [c * n * n for n in ns], "--", label=f"model $t_c n^2$, $t_c$ = {c * 1e9:.2f} ns")
    ax.set_xlabel("input size n")
    ax.set_ylabel("execution time (s)")
    ax.set_title("Sequential matrix-vector multiply (1 task)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig("task2_time_vs_n.png", dpi=150)
    return c


def task4(path, tc, ts, tw, n=32000):
    t = runs(path, re.compile(r"Running with (\d+) processes"))
    base = mean(t[1])
    print("\nTask 4/5: n=32000")
    print(f"{'p':>3} {'runs':>4} {'avg (s)':>10} {'min (s)':>10} {'speedup':>8} {'eff':>6} {'model S':>8}")
    ps, sp, model = [], [], []
    for p, v in t.items():
        a = mean(v)
        tp = tc * n * n / p + (ts * (p - 1).bit_length() + tw * n * (p - 1) / p if p > 1 else 0)
        ms = tc * n * n / tp
        print(f"{p:>3} {len(v):>4} {a:10.6f} {min(v):10.6f} {base / a:8.2f} {base / a / p:6.2f} {ms:8.2f}")
        ps.append(p); sp.append(base / a); model.append(ms)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(ps, ps, "k--", label="linear speedup")
    ax.plot(ps, model, ":", label="analytical model")
    ax.plot(ps, sp, "o-", label="measured")
    ax.set_xlabel("processes p")
    ax.set_ylabel("speedup $T_1/T_p$")
    ax.set_xticks(ps)
    ax.set_title("Parallel matrix-vector multiply, n = 32000")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig("task5_speedup.png", dpi=150)


def transpose(path):
    rows = []
    p = None
    for line in open(path):
        m = re.match(r"n=(\d+) p=(\d+) reps=(\d+)", line)
        if m and int(m.group(1)) > 8:
            p = int(m.group(2))
        m = re.match(r"avg\(s\)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", line)
        if m and p:
            rows.append((p, *map(float, m.groups())))
            p = None
    print("\nExtra credit: transpose (avg of reps, slowest rank)")
    print(f"{'p':>3} {'pack':>9} {'alltoall':>9} {'unpack':>9} {'total':>9} {'speedup':>8}")
    base = rows[0][4]
    for p, a, b, c, d in rows:
        print(f"{p:>3} {a:9.4f} {b:9.4f} {c:9.4f} {d:9.4f} {base / d:8.2f}")
    ps = [r[0] for r in rows]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    bottom = [0] * len(rows)
    for i, name in enumerate(["pack (local transpose)", "MPI_Alltoall", "unpack"]):
        vals = [r[i + 1] for r in rows]
        ax.bar([str(p) for p in ps], vals, bottom=bottom, label=name)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xlabel("processes p")
    ax.set_ylabel("time (s)")
    ax.set_title("Distributed transpose phase times")
    ax.legend()
    fig.tight_layout()
    fig.savefig("ec_transpose_phases.png", dpi=150)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    tc = task2(sys.argv[1])
    # on-node shared-memory MPI: ~1 us startup, ~5 GB/s per word of 8 bytes
    task4(sys.argv[2], tc, ts=1e-6, tw=8 / 5e9)
    transpose(sys.argv[3])
