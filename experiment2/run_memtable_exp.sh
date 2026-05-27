#!/bin/bash
# MemTable 크기 스윕 실험 (Write Stall 최소화 연구 — Part 1)
# 연구 질문: MemTable 크기가 커질수록 Write Stall이 어느 지점에서 수렴(포화)하는가?
# 측정: 쓰기 처리량(OPS), Write Stall 시간, WAF, 읽기 처리량

# ── [경로 설정] ─────────────────────────────────────────────────────────────
ROCKSDB_DIR="${HOME}/rocksdb"
DB_BENCH="${ROCKSDB_DIR}/db_bench"
export LD_LIBRARY_PATH="${ROCKSDB_DIR}:${LD_LIBRARY_PATH}"

BASE_DIR="${ROCKSDB_DIR}/experiment2/results"
LOG_DIR="${BASE_DIR}/memtable_logs"
AGG_DIR="${BASE_DIR}/aggregated"
BASE_DB="/tmp/rocksdb_mem_exp_db"
# ────────────────────────────────────────────────────────────────────────────

N_RUNS=3

# 총 쓰기: 10,000,000 × 1KB ≈ 9.5GB raw / Snappy 후 약 5GB
# 스레드당 2,500,000건으로 고정하여 총량 유지
NUM_KEYS=10000000
VAL_SIZE=1024
THREADS=4

# readrandom 단계 읽기 수 (스레드당)
# fillrandom 완료 후 동일 DB에서 읽기 성능 측정
READ_NUM=100000

# ── [--clean 처리] ─────────────────────────────────────────────────────────
RUN_CLEAN=false
for arg in "$@"; do
    if [ "$arg" == "--clean" ]; then
        RUN_CLEAN=true
    fi
done

if [ "${RUN_CLEAN}" = true ]; then
    echo "========================================"
    echo "  MemTable 실험 로그 삭제"
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

# ── [실험 목록: MemTable 크기 2MB~256MB, 8단계] ─────────────────────────────
# write_buffer_size: MemTable 하나의 크기 (기본값 64MB)
# 크기가 작을수록 flush가 잦아 L0 파일이 빠르게 누적 → Write Stall 심화
# 크기가 클수록 flush가 드물어 Stall 감소 → 어느 지점에서 효과 포화
EXPS=(
    "mem_2mb|--write_buffer_size=2097152"
    "mem_4mb|--write_buffer_size=4194304"
    "mem_8mb|--write_buffer_size=8388608"
    "mem_16mb|--write_buffer_size=16777216"
    "mem_32mb|--write_buffer_size=33554432"
    "mem_64mb|--write_buffer_size=67108864"
    "mem_128mb|--write_buffer_size=134217728"
    "mem_256mb|--write_buffer_size=268435456"
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

    # fillrandom: 랜덤 쓰기 후 statistics로 WAF·Stall 수집
    # readrandom: 동일 DB에서 읽기 성능 측정 (RAF 지표)
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
echo "  MemTable 크기 스윕 실험 (Part 1)"
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
echo "[취합] aggregate_memtable.py 실행 중..."
python3 "${ROCKSDB_DIR}/experiment2/aggregate_memtable.py"

echo ""
echo "========================================"
echo "  MemTable 실험 완료: $(date +"%Y-%m-%d %H:%M:%S")"
echo "========================================"
