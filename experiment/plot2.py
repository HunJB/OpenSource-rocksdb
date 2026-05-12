import sys
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
fm.fontManager.addfont('/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf')
matplotlib.rcParams['font.family'] = 'NanumBarunGothic'
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt

# ── 실험 폴더 결정 ─────────────────────────────────────────
# argv[1]로 직접 지정하거나, 없으면 latest_run.txt 참조
if len(sys.argv) > 1:
    run_id = sys.argv[1]
else:
    latest_path = './results/exp_data/latest_run.txt'
    if not os.path.exists(latest_path):
        print("❌ latest_run.txt 없음. run_id를 인자로 지정하거나 reader를 먼저 실행하세요.")
        sys.exit(1)
    with open(latest_path) as f:
        run_id = f.read().strip()

csv_path  = os.path.join('./results/exp_data', 'run_' + run_id, 'custom_movedist_batch.csv')
image_dir = os.path.join('./results/graph',    'run_' + run_id)

if not os.path.exists(csv_path):
    print(f"❌ 데이터 없음: {csv_path}")
    print("   reader를 먼저 실행하세요.")
    sys.exit(1)

df = pd.read_csv(csv_path)
os.makedirs(image_dir, exist_ok=True)

markers = ["o", "s", "^", "D", "x", "*"]
colors  = ["red", "blue", "green", "orange", "purple", "brown"]

plt.figure(figsize=(10, 6))

for i, (workload, group) in enumerate(df.groupby("workload")):
    group = group.sort_values("batch")
    plt.plot(
        group["batch"],
        group["hit_rate"],
        marker=markers[i % len(markers)],
        color=colors[i % len(colors)],
        lw=2,
        label=workload
    )

plt.xlabel("배치 번호")
plt.ylabel("Hit Rate (%)")
plt.title(f"배치별 Hit Rate (동적 분포)\n{run_id}")
plt.xticks(sorted(df["batch"].unique()))
plt.ylim(0, 100)
plt.grid(True, alpha=0.3)
plt.legend(fontsize=8)
plt.tight_layout()

out_path = os.path.join(image_dir, "hit_rate_by_batch.png")
plt.savefig(out_path, bbox_inches='tight')
print(f"✓ 저장: {out_path}")
