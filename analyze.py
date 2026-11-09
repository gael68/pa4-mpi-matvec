"""Parse the Bridges-2 job outputs in results/ and build tables and graphs.

usage: python3 analyze.py            (reads results/*.out, writes figures/ and pa4-data.xlsx)
"""
import glob
import math
import re
from collections import defaultdict
from statistics import mean, stdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font

TIME = re.compile(r"Parallel matrix vector multiplication time: ([\d.]+) sec")
plt.rcParams.update({"figure.figsize": (6.5, 4), "axes.grid": True, "grid.alpha": 0.3})


def one(pattern):
    files = sorted(glob.glob(f"results/{pattern}"))
    if not files:
        raise SystemExit(f"missing results/{pattern}")
    return files[-1]


def lines(path):
    return open(path).read().splitlines()


def sd(v):
    return stdev(v) if len(v) > 1 else 0.0


# ---------- parsers ----------

def parse_task1(path):
    rows, cur = [], None
    for ln in lines(path):
        if m := re.match(r"=== n=(\d+) np=(\d+)", ln):
            cur = {"n": int(m[1]), "p": int(m[2])}
            rows.append(cur)
        elif m := re.match(r"discrepancies: (\d+)", ln):
            cur["bad"] = int(m[1])
        elif m := re.match(r"Done with mvm, y\[(\d+)\] = ([\d.]+)", ln):
            cur["y"] = float(m[2])
        elif m := TIME.search(ln):
            cur["t"] = float(m[1])
    return rows


def closed_form(n):
    i = n - 1
    return 2 * i * n * (n - 1) // 2 + (n - 1) * n * (2 * n - 1) // 6


def times_by(path, header, key=lambda m: int(m[1])):
    out, k = defaultdict(list), None
    for ln in lines(path):
        if m := header.search(ln):
            k = key(m)
        elif (m := TIME.search(ln)) and k is not None:
            out[k].append(float(m[1]))
    return dict(sorted(out.items()))


def parse_transpose(path, section=None):
    """Return {p: (pack, alltoall, unpack, total)} of averages for the large-n runs."""
    out, p, n_seen, active = {}, None, None, section is None
    for ln in lines(path):
        if section and ln.startswith("#####"):
            active = section in ln
        if not active:
            continue
        if m := re.match(r"n=(\d+) p=(\d+) reps=", ln):
            p = int(m[2]) if int(m[1]) > 8 else None
            n_seen = int(m[1]) if p else n_seen
        elif (m := re.match(r"avg\(s\)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", ln)) and p:
            out[p] = tuple(map(float, m.groups()))
            p = None
    return n_seen, out


def parse_pingpong(path):
    blocks, cur = {}, None
    for ln in lines(path):
        if ln.startswith("##### pingpong"):
            cur = "same socket" if "same" in ln else "different sockets"
            blocks[cur] = []
        elif (m := re.match(r"pingpong (\d+) (\d+) ([\d.]+)", ln)) and cur:
            blocks[cur].append((int(m[1]), float(m[3]) * 1e-6))
    return blocks


def parse_allgather(path):
    out, on = {}, False
    for ln in lines(path):
        if ln.startswith("#####"):
            on = "allgather for mvm" in ln
        elif on and (m := re.match(r"allgather n=(\d+) p=(\d+) us=([\d.]+)", ln)):
            out[int(m[2])] = float(m[3]) * 1e-6
    return out


def parse_deep_breakdown(path):
    """{(n, p): [(max allgather, max compute, min compute, aggregate GB/s, driver time) per run]}"""
    out, key, ranks = defaultdict(list), None, []
    on = False
    for ln in lines(path):
        if ln.startswith("#####"):
            on = "allgather vs compute" in ln
            continue
        if not on:
            continue
        if m := re.match(r"=== n=(\d+) np=(\d+) run", ln):
            key, ranks = (int(m[1]), int(m[2])), []
        elif m := re.match(r"rank \d+ allgather_s ([\d.]+) compute_s ([\d.]+) GBps ([\d.]+)", ln):
            ranks.append(tuple(map(float, m.groups())))
        elif (m := TIME.search(ln)) and key:
            ag = max(r[0] for r in ranks)
            cmax = max(r[1] for r in ranks)
            cmin = min(r[1] for r in ranks)
            gbps = sum(r[2] for r in ranks)
            out[key].append((ag, cmax, cmin, gbps, float(m[1])))
    return dict(out)


def section(path, name):
    keep, on = [], False
    for ln in lines(path):
        if ln.startswith("#####"):
            on = name in ln
            continue
        if on:
            keep.append(ln)
    return keep


def times_in_section(path, name, header):
    out, k = defaultdict(list), None
    for ln in section(path, name):
        if m := header.search(ln):
            k = tuple(int(g) if g.isdigit() else g for g in m.groups())
            k = k[0] if len(k) == 1 else k
        elif (m := TIME.search(ln)) and k is not None:
            out[k].append(float(m[1]))
    return dict(out)


# ---------- main ----------

def main():
    import os
    os.makedirs("figures", exist_ok=True)
    f1, f2, f4 = one("task1-*.out"), one("task2-*.out"), one("task4-*.out")
    ftr, fx, fd = one("transpose-*.out"), one("extras-*.out"), one("deep-*.out")
    wb = Workbook()
    wb.remove(wb.active)

    def sheet(name, header, rows, note=None):
        ws = wb.create_sheet(name)
        r0 = 1
        if note:
            ws.cell(1, 1, note).font = Font(italic=True)
            r0 = 3
        for j, h in enumerate(header, 1):
            ws.cell(r0, j, h).font = Font(bold=True)
        for i, row in enumerate(rows, r0 + 1):
            for j, v in enumerate(row, 1):
                ws.cell(i, j, v)
        for j, h in enumerate(header, 1):
            ws.column_dimensions[ws.cell(r0, j).column_letter].width = max(12, len(h) + 2)

    # Task 1
    t1 = parse_task1(f1)
    print("Task 1 (correctness)")
    rows = []
    for r in t1:
        ok = r["bad"] == 0 and r["y"] == closed_form(r["n"])
        rows.append([r["n"], r["p"], r["bad"], r["y"], closed_form(r["n"]), "yes" if ok else "NO", r["t"]])
        print(f"  n={r['n']:>5} p={r['p']} discrepancies={r['bad']} y[n-1]={r['y']:.0f} closed-form match={ok} t={r['t']:.6f}")
    sheet("Task1 correctness", ["n", "p", "discrepancies", "y[n-1]", "closed form", "correct", "time (s)"], rows,
          f"Source: {f1}. Driver compares against a sequential product on rank 0.")

    # Task 2
    t2 = times_by(f2, re.compile(r"^=== n=(\d+)"))
    fine = times_in_section(fd, "sequential fine sweep", re.compile(r"^=== n=(\d+)"))
    ns = list(t2)
    avg2 = [mean(v) for v in t2.values()]
    tc = avg2[-1] / ns[-1] ** 2
    print(f"\nTask 2 (one task), t_c = {tc * 1e9:.3f} ns per multiply-add")
    rows, prev = [], None
    for n, v in t2.items():
        a = mean(v)
        rows.append([n, len(v), a, min(v), sd(v), a / n**2 * 1e9, a / prev if prev else None, tc * n * n])
        print(f"  n={n:>5} avg={a:.6f} min={min(v):.6f} sd={sd(v):.6f} t/n^2={a / n**2 * 1e9:.3f} ns ratio={a / prev if prev else 0:.2f}")
        prev = a
    sheet("Task2 sequential", ["n", "runs", "avg (s)", "min (s)", "stdev (s)", "avg/n^2 (ns)", "ratio to previous", "model t_c n^2 (s)"],
          rows, f"Source: {f2}. t_c fitted at n=32000.")
    sheet("Task2 fine sweep", ["n", "runs", "avg (s)", "avg/n^2 (ns)", "matrix MB"],
          [[n, len(v), mean(v), mean(v) / n**2 * 1e9, 8 * n * n / 1e6] for n, v in sorted(fine.items())],
          f"Source: {fd}. Same partition as Task 2.")

    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4))
    a.plot(ns, avg2, "o-", label="measured (avg of 5 runs)")
    xs = np.linspace(0, ns[-1], 200)
    a.plot(xs, tc * xs**2, "--", label=f"model $t_c n^2$, $t_c$={tc * 1e9:.2f} ns")
    a.set_xlabel("input size n"); a.set_ylabel("execution time (s)")
    a.set_title("Execution time vs n (1 task)"); a.legend()
    fn = sorted(fine)
    b.semilogx(fn, [mean(fine[n]) / n**2 * 1e9 for n in fn], "o-", label="fine sweep")
    b.semilogx(ns, [x / n**2 * 1e9 for n, x in zip(ns, avg2)], "s", label="Task 2 runs")
    b.axhline(tc * 1e9, ls="--", color="gray", label="$t_c$")
    for mb, lab in [(0.5, "A fits in L2 (512 KB)"), (16, "A fits in L3 (16 MB)")]:
        nn = math.sqrt(mb * 1e6 / 8)
        b.axvline(nn, color="gray", ls=":", lw=1)
        b.text(nn, b.get_ylim()[1] if False else 0.02, lab, rotation=90, va="bottom", ha="right", fontsize=8,
               transform=b.get_xaxis_transform())
    b.set_xlabel("input size n (log scale)"); b.set_ylabel("time / $n^2$ (ns)")
    b.set_title("Cost per matrix element"); b.legend(fontsize=8)
    fig.tight_layout(); fig.savefig("figures/task2_time_vs_n.png", dpi=150); plt.close(fig)

    # Communication parameters
    pp = parse_pingpong(fx)
    fits = {}
    for k, pts in pp.items():
        big = [(m, t) for m, t in pts if m >= 65536]
        slope, icpt = np.polyfit([m for m, _ in big], [t for _, t in big], 1)
        fits[k] = (pts[0][1], slope)
    ts, tw = fits["same socket"]
    print(f"\nPing-pong: same socket t_s={ts * 1e6:.3f} us t_w={tw * 1e9:.3f} ns/word; "
          f"different sockets t_s={fits['different sockets'][0] * 1e6:.3f} us t_w={fits['different sockets'][1] * 1e9:.3f} ns/word")
    rows = []
    for k, pts in pp.items():
        for m, t in pts:
            rows.append([k, m, m * 8, t * 1e6, m * 8 / t / 1e9])
    sheet("Pingpong", ["placement", "words", "bytes", "one-way (us)", "GB/s"], rows,
          f"Source: {fx}. t_s = smallest-message time; t_w = slope for m >= 65536 words.")
    fig, ax = plt.subplots()
    for k, pts in pp.items():
        ax.loglog([m * 8 for m, _ in pts], [t * 1e6 for _, t in pts], "o-", label=f"{k} (measured)")
        s0, w = fits[k]
        mm = np.logspace(0, math.log10(pts[-1][0]), 100)
        ax.loglog(mm * 8, (s0 + w * mm) * 1e6, ":", label=f"$t_s$={s0 * 1e6:.2f} µs, $t_w$={w * 1e9:.2f} ns/word")
    ax.set_xlabel("message size (bytes)"); ax.set_ylabel("one-way time (µs)")
    ax.set_title("Ping-pong between two ranks (Bridges-2 RM node)"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig("figures/pingpong.png", dpi=150); plt.close(fig)

    ag = parse_allgather(fx)
    n = 32000
    rows = [[p, t * 1e6, (ts * math.log2(p) + tw * n * (p - 1) / p) * 1e6] for p, t in ag.items()]
    sheet("Allgather n=32000", ["p", "measured (us)", "model t_s log p + t_w n(p-1)/p (us)"], rows, f"Source: {fx}.")

    # Task 4/5
    t4 = times_by(f4, re.compile(r"Running with (\d+) processes"))
    base = mean(t4[1])

    def model(p, n=32000):
        comm = 0 if p == 1 else ts * math.log2(p) + tw * n * (p - 1) / p
        return tc * n * n / p + comm

    print("\nTask 4/5 (n=32000, RM-shared)")
    rows, ps, sp, ms = [], [], [], []
    for p, v in t4.items():
        a = mean(v)
        rows.append([p, len(v), a, min(v), sd(v), base / a, base / a / p, model(p), model(1) / model(p)])
        ps.append(p); sp.append(base / a); ms.append(model(1) / model(p))
        print(f"  p={p} avg={a:.6f} min={min(v):.6f} speedup={base / a:.2f} eff={base / a / p:.2f} model={model(1) / model(p):.2f}")
    sheet("Task4 n=32000", ["p", "runs", "avg (s)", "min (s)", "stdev (s)", "speedup", "efficiency", "model T_p (s)", "model speedup"],
          rows, f"Source: {f4}. Model: t_c n^2/p + t_s log2 p + t_w n (p-1)/p with measured t_c, t_s, t_w.")

    place = times_in_section(fx, "placement", re.compile(r"=== map=(\w+) np=(\d+)"))
    full = times_in_section(fx, "default placement", re.compile(r"=== np=(\d+)"))
    fb = mean(full[1])
    spread = {p: fb / mean(place[("package", p)]) for p in (2, 4, 8)}
    spread[1] = 1.0
    fpl = one("placement-*.out")
    pl = times_in_section(fpl, "--map-by core", re.compile(r"=== map=\w+ np=(\d+)"))
    l3 = times_in_section(fpl, "--map-by l3cache", re.compile(r"=== map=\w+ np=(\d+)"))
    rows = []
    for name, d in (("core (default packing)", pl), ("l3cache (spread over CCXs)", l3)):
        for p in sorted(d):
            rows.append([name, p, len(d[p]), mean(d[p]), mean(d[1]) / mean(d[p]), mean(d[1]) / mean(d[p]) / p])
            print(f"  RM-shared --map-by {name:28} p={p} avg={mean(d[p]):.6f} speedup={mean(d[1]) / mean(d[p]):.2f}")
    sheet("Placement RM-shared", ["--map-by", "p", "runs", "avg (s)", "speedup", "efficiency"], rows,
          f"Source: {fpl}. Same 16-core allocation as mpi_submit; only rank placement differs.")
    # ceiling when all ranks sit on one 8-core chiplet (CCD), as in mpi_submit's runs
    bccd = 8 * 32000**2 / mean(place[("core", 8)])

    def model_bw(p, n=32000):
        comm = 0 if p == 1 else ts * math.log2(p) + tw * n * (p - 1) / p
        return n * n * max(tc / p, 8 / bccd) + comm

    print(f"  one-CCD bandwidth ceiling B = {bccd / 1e9:.1f} GB/s; refined model speedups: "
          + ", ".join(f"p={p}: {model_bw(1) / model_bw(p):.2f}" for p in ps))

    fig, ax = plt.subplots()
    ax.plot(ps, ps, "k--", label="linear speedup")
    ax.plot(ps, ms, ":", marker="^", label="analytical model (Task 3)")
    ax.plot(ps, [model_bw(1) / model_bw(p) for p in ps], "-.", marker="v",
            label=f"model with one-CCD bandwidth cap ({bccd / 1e9:.0f} GB/s)")
    ax.plot(ps, sp, "o-", lw=2, label="measured, mpi_submit (RM-shared)")
    sk = sorted(spread)
    ax.plot(sk, [spread[p] for p in sk], "s-", alpha=0.7, label="measured, ranks spread across sockets (full node)")
    ax.plot(ps, [mean(l3[1]) / mean(l3[p]) for p in ps], "D-", alpha=0.85,
            label="measured, --map-by l3cache (same 16 RM-shared cores)")
    ax.set_xticks(ps); ax.set_xlabel("processes p"); ax.set_ylabel("speedup $T_1/T_p$")
    ax.set_title("Matrix-vector multiply speedup, n = 32000"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig("figures/task5_speedup.png", dpi=150); plt.close(fig)

    # Placement and bandwidth
    rows = []
    for (mp, p), v in sorted(place.items()):
        rows.append([mp, p, mean(v), fb / mean(v), 8 * 32000**2 / mean(v) / 1e9])
    sheet("Placement n=32000", ["--map-by", "p", "avg (s)", "speedup vs full-node p=1", "aggregate GB/s"], rows,
          f"Source: {fx}. Exclusive RM node, 2 x AMD EPYC 7742.")
    rows = [[p, len(v), mean(v), fb / mean(v), fb / mean(v) / p, 8 * 32000**2 / mean(v) / 1e9] for p, v in sorted(full.items())]
    sheet("Scaling to 64", ["p", "runs", "avg (s)", "speedup", "efficiency", "aggregate GB/s"], rows,
          f"Source: {fx}. Default mapping on an exclusive node.")
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4))
    for mp, lab in [("core", "packed on neighbouring cores"), ("package", "spread across sockets")]:
        pp_ = [1, 2, 4, 8]
        bw = [8 * 32000**2 / fb / 1e9] + [8 * 32000**2 / mean(place[(mp, p)]) / 1e9 for p in (2, 4, 8)]
        a.plot(pp_, bw, "o-", label=lab)
    a.set_xticks([1, 2, 4, 8]); a.set_xlabel("processes p"); a.set_ylabel("matrix streamed (GB/s)")
    a.set_title("Memory bandwidth used by mvm, n = 32000"); a.legend(fontsize=8)
    fp = sorted(full)
    b.plot(fp, fp, "k--", label="linear")
    b.plot(fp, [fb / mean(full[p]) for p in fp], "o-", label="measured (default placement)")
    b.set_xscale("log", base=2); b.set_yscale("log", base=2)
    b.set_xticks(fp); b.set_xticklabels(fp); b.set_yticks(fp); b.set_yticklabels(fp)
    b.set_xlabel("processes p"); b.set_ylabel("speedup"); b.set_title("Scaling past p = 8 (full node)"); b.legend(fontsize=8)
    fig.tight_layout(); fig.savefig("figures/placement_bandwidth.png", dpi=150); plt.close(fig)

    # Breakdown
    bd = parse_deep_breakdown(fd)
    print("\nAllgather vs compute (max over ranks, avg of runs)")
    rows = []
    for (nn, p), runs_ in sorted(bd.items()):
        agm = mean(r[0] for r in runs_); cm = mean(r[1] for r in runs_)
        cmin = mean(r[2] for r in runs_); gb = mean(r[3] for r in runs_); drv = mean(r[4] for r in runs_)
        comm_model = 0 if p == 1 else ts * math.log2(p) + tw * nn * (p - 1) / p
        rows.append([nn, p, agm * 1e6, comm_model * 1e6, cm, tc * nn * nn / p, cmin, 100 * agm / (agm + cm), gb, drv])
        print(f"  n={nn:>5} p={p} allgather={agm * 1e6:9.1f} us (model {comm_model * 1e6:7.1f}) compute={cm:.6f} "
              f"(model {tc * nn * nn / p:.6f}) comm%={100 * agm / (agm + cm):5.1f} GB/s={gb:.1f}")
    sheet("Allgather vs compute", ["n", "p", "allgather max (us)", "model comm (us)", "compute max (s)", "model compute (s)",
                                   "compute min (s)", "comm % of total", "aggregate GB/s", "driver-reported time (s)"],
          rows, f"Source: {fd}. Instrumented copy of mvm.c (mvm_timed.c); RM-shared, 16 cores.")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, nn in zip(axes, (1000, 32000)):
        pp_ = sorted(p for (x, p) in bd if x == nn)
        agv = [mean(r[0] for r in bd[(nn, p)]) * 1e3 for p in pp_]
        cv = [mean(r[1] for r in bd[(nn, p)]) * 1e3 for p in pp_]
        lbl = [str(p) for p in pp_]
        ax.bar(lbl, cv, label="local multiply")
        ax.bar(lbl, agv, bottom=cv, label="MPI_Allgather")
        for i, (c_, g_) in enumerate(zip(cv, agv)):
            ax.text(i, c_ + g_, f"{100 * g_ / (c_ + g_):.1f}% comm", ha="center", va="bottom", fontsize=8)
        ax.set_xlabel("processes p"); ax.set_ylabel("time (ms)"); ax.set_title(f"n = {nn}")
        ax.legend(fontsize=8)
    fig.suptitle("Where MatrixVectorMultiply spends its time (slowest rank)")
    fig.tight_layout(); fig.savefig("figures/mvm_breakdown.png", dpi=150); plt.close(fig)

    # Transpose
    n16, tiled = parse_transpose(ftr, "timing, tiled")
    _, untiled = parse_transpose(ftr, "timing, untiled")
    n32, tr32 = parse_transpose(fx, "transpose n=32000")
    sweep, cur = defaultdict(dict), None
    for ln in section(ftr, "tile size sweep"):
        if m := re.match(r"n=\d+ p=(\d+) reps=\d+ tile=(\d+)", ln):
            cur = (int(m[1]), int(m[2]))
        elif (m := re.match(r"avg\(s\)\s+([\d.]+)", ln)) and cur:
            sweep[cur[0]][cur[1]] = float(m[1])
    print("\nTranspose")
    rows = []
    for label, nn, tr, src in [("RM-shared, tiled (tile 64)", n16, tiled, ftr),
                               ("RM-shared, untiled", n16, untiled, ftr),
                               ("RM full node, untiled", n32, tr32, fx)]:
        b0 = tr[1][3]
        for p, (pk, a2a, up, tot) in sorted(tr.items()):
            ns_el = pk / (nn * nn / p) * 1e9
            rows.append([label, nn, p, pk, a2a, up, tot, b0 / tot, ns_el, 8 * nn * nn / p / 1e9])
            print(f"  {label:28} n={nn} p={p:>2} pack={pk:.4f} ({ns_el:.2f} ns/elem) alltoall={a2a:.4f} "
                  f"unpack={up:.4f} total={tot:.4f} speedup={b0 / tot:.2f}")
    sheet("Transpose", ["run", "n", "p", "pack (s)", "alltoall (s)", "unpack (s)", "total (s)", "speedup",
                        "pack ns/element", "GB per rank"],
          rows, f"Sources: {ftr}, {fx}. Averages over reps, slowest rank per phase.")
    sheet("Transpose tile sweep", ["p", "tile", "pack (s)", "pack ns/element"],
          [[p, t, v, v / (n16 * n16 / p) * 1e9] for p in sorted(sweep) for t, v in sorted(sweep[p].items())],
          f"Source: {ftr}. n={n16}.")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, (tr, title) in zip(axes, [(untiled, "untiled local transpose"), (tiled, "tiled local transpose (64x64)")]):
        pp_ = sorted(tr)
        bottom = np.zeros(len(pp_))
        for i, name in enumerate(["local transpose (pack)", "MPI_Alltoall", "unpack"]):
            v = np.array([tr[p][i] for p in pp_])
            ax.bar([str(p) for p in pp_], v, bottom=bottom, label=name)
            bottom += v
        ax.set_xlabel("processes p"); ax.set_ylabel("time (s)"); ax.set_title(f"n = {n16}, {title}")
        ax.legend(fontsize=8)
    top = max(max(untiled[p][3] for p in untiled), max(tiled[p][3] for p in tiled)) * 1.08
    for ax in axes:
        ax.set_ylim(0, top)
    fig.suptitle("Distributed transpose: time per phase (RM-shared)")
    fig.tight_layout(); fig.savefig("figures/transpose_phases.png", dpi=150); plt.close(fig)

    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4))
    pp_ = sorted(tiled)
    a.plot(pp_, pp_, "k--", label="linear")
    a.plot(pp_, [tiled[1][3] / tiled[p][3] for p in pp_], "o-", label=f"tiled, n={n16}")
    a.plot(pp_, [untiled[1][3] / untiled[p][3] for p in pp_], "s-", label=f"untiled, n={n16}")
    a.set_xticks(pp_); a.set_xlabel("processes p"); a.set_ylabel("speedup"); a.set_title("Transpose speedup (RM-shared)")
    a.legend(fontsize=8)
    for p in sorted(sweep):
        ts_ = sorted(sweep[p])
        b.semilogx(ts_, [sweep[p][t] / (n16 * n16 / p) * 1e9 for t in ts_], "o-", base=2, label=f"p={p}")
    b.set_xticks([8, 16, 32, 64, 128, 256]); b.set_xticklabels([8, 16, 32, 64, 128, 256])
    b.set_xlabel("tile side (elements)"); b.set_ylabel("pack time per element (ns)")
    b.set_title(f"Local transpose cost vs tile size, n={n16}"); b.legend(fontsize=8)
    fig.tight_layout(); fig.savefig("figures/transpose_speedup.png", dpi=150); plt.close(fig)

    sheet("Model parameters", ["parameter", "value", "unit", "how measured"], [
        ["t_c", tc * 1e9, "ns per multiply-add", "Task 2, n=32000 time / n^2"],
        ["t_s (same socket)", ts * 1e6, "us", "ping-pong, 8-byte message"],
        ["t_w (same socket)", tw * 1e9, "ns per 8-byte word", "ping-pong slope, >= 512 KB"],
        ["t_s (different sockets)", fits["different sockets"][0] * 1e6, "us", "ping-pong, 8-byte message"],
        ["t_w (different sockets)", fits["different sockets"][1] * 1e9, "ns per 8-byte word", "ping-pong slope, >= 512 KB"],
    ])
    wb.move_sheet("Model parameters", offset=-len(wb.sheetnames) + 1)
    wb.save("pa4-data.xlsx")
    print("\nwrote pa4-data.xlsx and figures/*.png")


if __name__ == "__main__":
    main()
