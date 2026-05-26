#!/bin/bash
# Write Stall 3요소 비교 실험 스크립트
# 측정 목표: Input 과다 / MemTable 크기 / L0 수용 한계 중 어떤 요소가 가장 심한 Write Stall을 유발하는가
# 각 시나리오를 N_RUNS회 다른 랜덤 시드로 반복하여 통계적 신뢰도 확보

# ── [경로 설정] ─────────────────────────────────────────
ROCKSDB_DIR="${HOME}/rocksdb"
DB_BENCH="${ROCKSDB_DIR}/db_bench"
export LD_LIBRARY_PATH="${ROCKSDB_DIR}:${LD_LIBRARY_PATH}"

BASE_DIR="${ROCKSDB_DIR}/experiment2/results"
LOG_DIR="${BASE_DIR}/logs"
AGG_DIR="${BASE_DIR}/aggregated"
BASE_DB="/tmp/rocksdb_stall_exp_db"
# ────────────────────────────────────────────────────────

# 각 시나리오당 반복 횟수 (다른 랜덤 시드로 측정 → aggregate_3factor.py 에서 평균 계산)
N_RUNS=3

# Factor 1 전용: 모든 실험을 동일한 시간 창으로 고정
# 같은 시간 동안 스레드가 많을수록 더 많은 데이터를 DB에 밀어넣어 진정한 "입력 과다" 재현
# (--num 분배 방식은 총량이 같아 압박 차이 없음 → --duration 기반으로 대체)
DURATION_INPUT=120

RUN_CLEAN=false
for arg in "$@"; do
    if [ "$arg" == "--clean" ]; then
        RUN_CLEAN=true
    fi
done

if [ "${RUN_CLEAN}" = true ]; then
    echo "========================================"
    echo "  기존 실험 결과(로그) 및 임시 데이터 삭제"
    echo "  (※ 시각화된 그래프 이미지 파일은 보존됩니다)"
    echo "========================================"
    if [ -d "${LOG_DIR}" ]; then
        find "${LOG_DIR}" -name "*.log" -delete
        echo "✓ 실험 로그 삭제 완료 (${LOG_DIR})"
    fi
    rm -rf "${BASE_DB}"*
    echo "✓ 임시 DB 디렉토리 정리 완료"
    echo "========================================"
    exit 0
fi

# ── [실험 목록: 3요소 비교, 요소별 3강도 + 기준선 = 총 10개] ─
EXPS=(
    # 대조군 (threads=4, 모든 기본값 유지)
    "exp0_baseline|--threads=4"

    # Factor 1: Input 과다 — 동일 시간(DURATION_INPUT초) 동안 스레드 수 증가 → 단위 시간당 쓰기 요청 증가
    # --duration으로 시간 창을 고정하고 --num은 실질적으로 무제한(999999999)으로 설정
    # → 스레드가 많을수록 같은 시간에 더 많은 데이터를 DB에 밀어넣어 진정한 압박 차이 발생
    "exp1a_input_threads8|--threads=8 --duration=${DURATION_INPUT}"
    "exp1b_input_threads16|--threads=16 --duration=${DURATION_INPUT}"
    "exp1c_input_threads32|--threads=32 --duration=${DURATION_INPUT}"

    # Factor 2: MemTable 크기 축소 — 잦은 Flush → L0 파일 누적 가속 → Stall 유발
    # 기본값 64MB에서 단계적 축소 (threads=4 고정으로 Factor 1 영향 배제)
    "exp2a_mem_16mb|--threads=4 --write_buffer_size=16777216"
    "exp2b_mem_4mb|--threads=4 --write_buffer_size=4194304"
    "exp2c_mem_2mb|--threads=4 --write_buffer_size=2097152"

    # Factor 3: L0 수용 한계 축소 — Stall 발동 임계값 조기화 (threads=4 고정)
    # 기본값(slowdown=20, stop=36)에서 단계적 하향
    "exp3a_l0_12_24|--threads=4 --level0_slowdown_writes_trigger=12 --level0_stop_writes_trigger=24"
    "exp3b_l0_8_16|--threads=4 --level0_slowdown_writes_trigger=8 --level0_stop_writes_trigger=16"
    "exp3c_l0_4_8|--threads=4 --level0_slowdown_writes_trigger=4 --level0_stop_writes_trigger=8"
)
# ────────────────────────────────────────────────────────

mkdir -p "${LOG_DIR}"
mkdir -p "${AGG_DIR}"

# 총 쓰기 목표: NUM_KEYS × VAL_SIZE = 10,000,000 × 1KB ≈ 9.5GB
# per_thread_num = NUM_KEYS / thread_count 로 분배하여 스레드 수와 무관하게 총량 일정 유지
# → Write Stall 측정을 위해 최소 5GB 이상 필요 (교수님 권고)
NUM_KEYS=10000000
VAL_SIZE=1024

# 특정 시나리오의 완료된 실험 횟수를 반환
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

    local thread_count
    thread_count=$(echo "$extra_args" | sed -n 's/.*--threads=\([0-9]*\).*/\1/p')
    if [ -z "$thread_count" ]; then
        thread_count=4
    fi

    # --duration이 있으면 시간 기반 실행 (Factor 1 전용)
    # --num을 사실상 무제한으로 설정해야 duration이 만료될 때까지 계속 쓰기를 시도함
    local num_arg
    if echo "$extra_args" | grep -q -- '--duration='; then
        num_arg=${NUM_KEYS}
        echo ""
        echo "[진행 중] ${exp_name}  (Run ${run_num}/${N_RUNS} | seed=${seed} | ${thread_count}T × ${DURATION_INPUT}초 duration 기반)"
    else
        num_arg=$(( NUM_KEYS / thread_count ))
        echo ""
        echo "[진행 중] ${exp_name}  (Run ${run_num}/${N_RUNS} | seed=${seed} | ${thread_count}T × ${num_arg}건)"
    fi

    rm -rf "${BASE_DB}"

    ${DB_BENCH} \
        --benchmarks=fillrandom \
        --db="${BASE_DB}" \
        --num=${num_arg} \
        --value_size=${VAL_SIZE} \
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
echo "  Write Stall 3요소 비교 실험"
echo "  시나리오당 ${N_RUNS}회 반복 측정 (랜덤 시드 변경)"
echo "  로그 저장: ${LOG_DIR}"
echo "========================================"

# ── [메인 루프: 완료 횟수 기반 자동 이어하기] ───────────────
# 각 시나리오마다 completed 횟수를 확인하고 N_RUNS가 될 때까지 자동 실행
# 중단 후 재실행해도 부족한 횟수만큼만 추가 실행됨 (수동 y/n 불필요)
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
echo "[취합] aggregate_3factor.py 실행 중..."
python3 "${ROCKSDB_DIR}/experiment2/aggregate_3factor.py"

echo ""
echo "========================================"
echo "  모든 실험 및 시각화 완료: $(date +"%Y-%m-%d %H:%M:%S")"
echo "========================================"
