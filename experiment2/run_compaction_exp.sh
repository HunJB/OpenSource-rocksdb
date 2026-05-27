#!/bin/bash
# Compaction 조건 변화 실험 (Write Stall 최소화 연구 — Part 2)
# 연구 질문: Compaction 조건을 어떻게 조정하면 Write Stall과 Read/Write 증폭을
#            동시에 최적화할 수 있는가?
# 하위 그룹: A(BG스레드) B(L0트리거) C(레벨크기) D(알고리즘) E(Pending바이트)

# ── [경로 설정] ─────────────────────────────────────────────────────────────
ROCKSDB_DIR="${HOME}/rocksdb"
DB_BENCH="${ROCKSDB_DIR}/db_bench"
export LD_LIBRARY_PATH="${ROCKSDB_DIR}:${LD_LIBRARY_PATH}"

BASE_DIR="${ROCKSDB_DIR}/experiment2/results"
LOG_DIR="${BASE_DIR}/compaction_logs"
AGG_DIR="${BASE_DIR}/aggregated"
BASE_DB="/tmp/rocksdb_comp_exp_db"
# ────────────────────────────────────────────────────────────────────────────

N_RUNS=3

# 총 쓰기: 5,000,000 × 1KB ≈ 4.8GB raw / Snappy 후 약 2.5GB
# (10M에서 5M으로 축소: max_background_jobs가 높을 때 복수 Compaction이 동시 실행되어
#  입력 + 출력 파일이 공존하며 피크 디스크 사용량이 7GB를 초과하는 문제 방지)
NUM_KEYS=5000000
VAL_SIZE=1024
THREADS=4
READ_NUM=100000

# ── [--clean 처리] ──────────────────────────────────────────────────────────
RUN_CLEAN=false
for arg in "$@"; do
    if [ "$arg" == "--clean" ]; then
        RUN_CLEAN=true
    fi
done

if [ "${RUN_CLEAN}" = true ]; then
    echo "========================================"
    echo "  Compaction 실험 로그 삭제"
    echo "  (※ 그래프 이미지는 보존됩니다)"
    echo "========================================"
    if [ -d "${LOG_DIR}" ]; then
        find "${LOG_DIR}" -name "*.log" -delete
        echo "✓ 로그 삭제 완료 (${LOG_DIR})"
    fi
    rm -rf "${BASE_DB}"*
    echo "✓ 임시 DB 정리 완료"
    echo "========================================"
    exit 0
fi

# ── [실험 목록: 5개 그룹, 총 19개 시나리오] ─────────────────────────────────
EXPS=(
    # ── [Group A] 백그라운드 Compaction 스레드 수 ────────────────────────────
    # max_background_jobs = 플러시 스레드(1) + 컴팩션 스레드(N-1)
    # 스레드 수 증가 → Compaction 속도 향상 → L0 적체 감소 → Stall 감소
    # 단, CPU 경합으로 수확 체감 발생 → 최적 스레드 수 탐색
    "comp_bg1|--max_background_jobs=2"
    "comp_bg2|--max_background_jobs=3"
    "comp_bg4|--max_background_jobs=5"
    "comp_bg8|--max_background_jobs=9"

    # ── [Group B] L0 파일 수 트리거 임계값 ───────────────────────────────────
    # level0_slowdown_writes_trigger: L0 파일 수가 이 값 초과 시 쓰기 속도 제한
    # level0_stop_writes_trigger:     L0 파일 수가 이 값 초과 시 쓰기 완전 중단
    # 임계값 낮음 → 조기 Stall, 높은 Read 성능 / 높음 → 드문 Stall, 낮은 Read 성능
    "comp_l0_4_8|--level0_slowdown_writes_trigger=4 --level0_stop_writes_trigger=8"
    "comp_l0_12_24|--level0_slowdown_writes_trigger=12 --level0_stop_writes_trigger=24"
    "comp_l0_20_36|--level0_slowdown_writes_trigger=20 --level0_stop_writes_trigger=36"
    "comp_l0_40_80|--level0_slowdown_writes_trigger=40 --level0_stop_writes_trigger=80"
    "comp_l0_80_160|--level0_slowdown_writes_trigger=80 --level0_stop_writes_trigger=160"

    # ── [Group C] 레벨 크기 및 배율 조정 ────────────────────────────────────
    # max_bytes_for_level_base: L1 최대 크기 (기본 256MB)
    # max_bytes_for_level_multiplier: 레벨당 크기 배율 (기본 10)
    # L1 작음 → 자주 컴팩션 → WAF 증가 / L1 큼 → 드물게 컴팩션 → RAF 증가
    "comp_lvl_small|--max_bytes_for_level_base=67108864 --max_bytes_for_level_multiplier=5"
    "comp_lvl_default|--max_bytes_for_level_base=268435456 --max_bytes_for_level_multiplier=10"
    "comp_lvl_large|--max_bytes_for_level_base=1073741824 --max_bytes_for_level_multiplier=10"
    "comp_lvl_mult20|--max_bytes_for_level_base=268435456 --max_bytes_for_level_multiplier=20"

    # ── [Group D] Compaction 알고리즘 ────────────────────────────────────────
    # Level-based(0): 기본값, 레벨 구조 유지, 높은 WAF
    # Universal(1): 모든 파일을 순차적으로 병합, 낮은 WAF, 높은 공간 증폭
    "comp_style_leveled|--compaction_style=0"
    "comp_style_universal|--compaction_style=1"

    # ── [Group E] Pending Compaction 바이트 임계값 ───────────────────────────
    # soft_pending_compaction_bytes_limit: 이 값 초과 시 쓰기 속도 제한
    # hard_pending_compaction_bytes_limit: 이 값 초과 시 쓰기 완전 중단
    # 임계값 낮으면 → 조기 Stall, Compaction 부채 억제
    # 임계값 높으면 → Stall 늦게 발동, 부채 누적 후 폭발적 Compaction
    "comp_pend_very_tight|--soft_pending_compaction_bytes_limit=67108864 --hard_pending_compaction_bytes_limit=268435456"
    "comp_pend_tight|--soft_pending_compaction_bytes_limit=536870912 --hard_pending_compaction_bytes_limit=2147483648"
    "comp_pend_loose|--soft_pending_compaction_bytes_limit=4294967296 --hard_pending_compaction_bytes_limit=17179869184"
    "comp_pend_default|--soft_pending_compaction_bytes_limit=68719476736 --hard_pending_compaction_bytes_limit=274877906944"
)
# ────────────────────────────────────────────────────────────────────────────

mkdir -p "${LOG_DIR}" "${AGG_DIR}"

per_thread_num=$(( NUM_KEYS / THREADS ))

# 특정 시나리오의 완료된 실험 횟수 반환 (이어하기용)
count_completed() {
    local exp_name=$1
    local count=0
    for f in "${LOG_DIR}/${exp_name}_"*.log; do
        [ -f "$f" ] || continue
        if grep -q "\[EXPERIMENT_COMPLETED\]" "$f" 2>/dev/null; then
            count=$(( count + 1 ))
        fi
    done
    echo "$count"
}

run_experiment() {
    local exp_name=$1
    local extra_args=$2
    local run_num=$3
    local seed
    seed=$(date +%s%N)
    local timestamp
    timestamp=$(date +"%Y%m%d_%H%M%S")
    local log_file="${LOG_DIR}/${exp_name}_${timestamp}.log"

    echo ""
    echo "[진행 중] ${exp_name}  (Run ${run_num}/${N_RUNS} | seed=${seed})"
    rm -rf "${BASE_DB}"

    # fillrandom: 랜덤 쓰기 (WAF·Stall 측정)
    # readrandom: 동일 DB 읽기 (RAF 프록시 측정)
    ${DB_BENCH} \
        --benchmarks=fillrandom,readrandom \
        --db="${BASE_DB}" \
        --num=${per_thread_num} \
        --reads=${READ_NUM} \
        --threads=${THREADS} \
        --value_size=${VAL_SIZE} \
        --statistics=1 \
        --stats_interval_seconds=1 \
        --seed=${seed} \
        ${extra_args} > "${log_file}" 2>&1

    if [ $? -eq 0 ]; then
        echo "✓ 완료 -> $(basename "${log_file}")"
        echo "[EXPERIMENT_COMPLETED]" >> "${log_file}"
    else
        echo "❌ 실패 -> $(basename "${log_file}")"
    fi
}

echo "========================================"
echo "  Compaction 조건 변화 실험 (Part 2)"
echo "  시나리오: ${#EXPS[@]}개 × ${N_RUNS}회 반복"
echo "  쓰기: ${NUM_KEYS}건 (${THREADS}T × ${per_thread_num}건/T)"
echo "  읽기: ${READ_NUM}건/T (fillrandom 완료 후)"
echo "  로그 저장: ${LOG_DIR}"
echo "========================================"

# ── [메인 루프: 완료 횟수 기반 자동 이어하기] ────────────────────────────────
for i in "${!EXPS[@]}"; do
    EXP_NAME="${EXPS[$i]%%|*}"
    EXP_ARGS="${EXPS[$i]#*|}"

    completed=$(count_completed "$EXP_NAME")
    remaining=$(( N_RUNS - completed ))

    if [ "$remaining" -le 0 ]; then
        echo "[SKIP] ${EXP_NAME}: 이미 ${N_RUNS}/${N_RUNS}회 완료"
        continue
    fi

    echo ""
    echo "── ${EXP_NAME}: ${completed}/${N_RUNS}회 완료, ${remaining}회 남음 ──"

    for run in $(seq 1 "$remaining"); do
        run_num=$(( completed + run ))
        run_experiment "$EXP_NAME" "$EXP_ARGS" "$run_num"
    done
done

rm -rf "${BASE_DB}"

echo ""
echo "[취합] aggregate_compaction.py 실행 중..."
python3 "${ROCKSDB_DIR}/experiment2/aggregate_compaction.py"

echo ""
echo "========================================"
echo "  Compaction 실험 완료: $(date +"%Y-%m-%d %H:%M:%S")"
echo "========================================"
