import sys, statistics, math, json, random
sys.path.insert(0, '/home/claude/warwatch/warwatch')
import engine as E, stats
print("S1 OWA weights at orness 0.3 (rank 1 = strongest):")
for n in (2, 3, 4, 6):
    print(n, [round(w, 3) for w in E.owa_weights(n)])
print("domain score: one group at +5, rest 0:", {n: round(E.domain_score([5] + [0]*(n-1))[0], 2) for n in (1, 2, 3, 6)})
print("domain score: two at +4, rest 0 (6 groups):", round(E.domain_score([4, 4, 0, 0, 0, 0])[0], 2))
print("domain score: one at +5, rest at -0.5 (6 groups):", round(E.domain_score([5, -0.5, -0.5, -0.5, -0.5, -0.5])[0], 2))
print("Yemen info domain live: [5,1.78,1.24,...]")
print("S2 MPI compensation (Yemen 2024-01-10 replay profile, weights .3 .1 .1 .3):")
m, s, i = E.mpi([-3.25, 3.5, 0.72, 0.44], [.3, .1, .1, .3]); print(' MPI z =', round((i-100)/10, 2), 'M', round(m, 2), 'S', round(s, 2))
m, s, i = E.mpi([0, 3.5, 0.72, 0.44], [.3, .1, .1, .3]); print(' with negatives floored at 0: z =', round((i-100)/10, 2))
print("S3 multiple comparisons, 13 theatres independent at nominal rates:")
for lvl, p in (("Watch", .10), ("Elevated", .05), ("Critical", .01)):
    print(' P(global >=', lvl, ') =', round(1 - (1-p)**13, 3))
# S5 slow build-up: 60-day linear ramp of +3 sd on noise
rnd = random.Random(1)
base = [100 + rnd.gauss(0, 5) for _ in range(200)]
import datetime as dt
d0 = dt.date(2024, 1, 1)
ramp = [v + (min(max(i - 200 + 120, 0), 60) / 60 * 15 if i >= 80 else 0) for i, v in enumerate(base + [100 + rnd.gauss(0, 5) for _ in range(40)])]
# build series: 200 calm days then build-up from day 200..260? simpler explicit:
vals = [100 + rnd.gauss(0, 5) for _ in range(150)] + [100 + 15 * k / 60 + rnd.gauss(0, 5) for k in range(1, 91)]   # 90-day ramp to +3 sd (plateau after 60? no: keeps rising to +22)
pts = [((d0 + dt.timedelta(days=i)).isoformat(), v) for i, v in enumerate(vals)]
traj = []
for k in range(150, len(pts) + 1, 10):
    r = stats.score_series(pts[:k], 'daily'); traj.append((k - 150, round(r['z'], 2) if r else None))
print("S5 linear build-up of 15 units (3 sd of daily noise) every 60 days; v7 z by day of build-up:", traj)
# CUSUM on standardised daily values vs frozen pre-build baseline
mu = statistics.fmean(vals[:150]); sd = statistics.pstdev(vals[:150]); k = 0.5; S = 0; cus = []
for i, v in enumerate(vals[150:]):
    S = max(0, S + (v - mu) / sd - k)
    if i % 10 == 0: cus.append((i, round(S, 1)))
print("   CUSUM (k=0.5, frozen baseline) by day:", cus)
