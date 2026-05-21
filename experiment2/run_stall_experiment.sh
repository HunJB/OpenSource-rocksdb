#!/bin/bash
# 쓰기 지연(Write Stall) 자동화 실험 스크립트 (총 10개 시나리오)
# 기능: 중단 감지 시 무조건 (y/n)으로 물어보며, 'n' 선택 시 0번부터 전체 재시작

# ── [경로 설정] ─────────────────────────────────────────
ROCKSDB_DIR="${HOME}/rocksdb"
DB_BENCH="${ROCKSDB_DIR}/db_bench"
export LD_LIBRARY_PATH="${ROCKSDB_DIR}:${LD_LIBRARY_PATH}"

BASE_DIR="${ROCKSDB_DIR}/experiment2/results"
LOG_DIR="${BASE_DIR}/logs"
AGG_DIR="${BASE_DIR}/aggregated"
BASE_DB="/tmp/rocksdb_stall_exp_db"
# ────────────────────────────────────────────────────────

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
        rm -rf "${LOG_DIR}"
        echo "✓ 실험 로그 삭제 완료 (${LOG_DIR})"
    fi
    rm -rf "${BASE_DB}"*
    echo "✓ 임시 DB 디렉토리 정리 완료"
    echo "========================================"
    exit 0
fi

# ── [실험 목록 배열 정의] ───────────────────────────────
EXPS=(
    # 0. 기본값 (비교용 대조군, 어떠한 추가 옵션도 주지 않은 순정 상태)
    "exp0_default|"
    
    # 1. 단일 스레드 (스레드 동시성 경합 없음, 200만회에서는 결과 역전 발생)
    "exp1_thread_1|--threads=1"
    
    # 2. 중간 스레드 (적당한 경합 유발)
    "exp2_thread_8|--threads=8"
    
    # 3. 과다 스레드 (극심한 락 경합 유발)
    "exp3_thread_16|--threads=16"
    
    # 4. 작은 MemTable (2MB로 설정하여 잦은 Flush 유발)
    "exp4_small_memtable|--threads=4 --write_buffer_size=2097152"
    
    # 5. 낮은 L0 한계 (Level 0 파일이 4개/8개일 때 Stall 강제 유발)
    "exp5_low_l0_limit|--threads=4 --level0_slowdown_writes_trigger=4 --level0_stop_writes_trigger=8"
    
    # 6. Pending Compaction 병목 (백그라운드 스레드를 1개로 제한하여 지연)
    "exp6_pending_compaction|--threads=4 --max_background_compactions=1 --soft_pending_compaction_bytes_limit=67108864 --hard_pending_compaction_bytes_limit=134217728"
    
    # 7. Universal Compaction (쓰기 증폭을 줄이는 병합 알고리즘 적용)
    "exp7_universal_compaction|--threads=4 --compaction_style=1"
    
    # 8. Direct I/O (OS 페이지 캐시를 우회하여 디스크 직접 쓰기)
    "exp8_direct_io|--threads=4 --use_direct_io_for_flush_and_compaction=true"
    
    # 9. Sync Commit (모든 쓰기마다 fsync 강제, 최대 60초만 실행)
    "exp9_sync_commit|--threads=4 --sync=1 --duration=60"
)
# ────────────────────────────────────────────────────────

mkdir -p "${LOG_DIR}"
mkdir -p "${AGG_DIR}"

NUM_KEYS=10000000
VAL_SIZE=1024

# ── [핵심: 가장 최근 작업 시점 찾기 및 사용자 질문] ────────
START_INDEX=0
NEWEST_LOG=$(ls -t "${LOG_DIR}"/*.log 2>/dev/null | head -n 1)

if [ -n "$NEWEST_LOG" ]; then
    IS_COMPLETED=false
    if grep -q "\[EXPERIMENT_COMPLETED\]" "$NEWEST_LOG"; then
        IS_COMPLETED=true
    fi

    MATCHED_INDEX=-1
    BASENAME=$(basename "$NEWEST_LOG")
    
    for i in "${!EXPS[@]}"; do
        EXP_NAME="${EXPS[$i]%%|*}"
        if [[ "$BASENAME" == "${EXP_NAME}"_* ]]; then
            MATCHED_INDEX=$i
            break
        fi
    done

    if [ "$MATCHED_INDEX" -ne -1 ]; then
        if [ "$IS_COMPLETED" = true ]; then
            if [ "$MATCHED_INDEX" -eq $(( ${#EXPS[@]} - 1 )) ]; then
                echo "💡 이전 10개의 실험 세트가 모두 완료된 것을 확인했습니다. 처음부터 새로 시작합니다."
                START_INDEX=0
            else
                NEXT_INDEX=$(( MATCHED_INDEX + 1 ))
                echo "========================================"
                read -p "💡 이전 실행이 [${EXPS[$MATCHED_INDEX]%%|*}] 까지 완료되었습니다. 다음인 [${EXPS[$NEXT_INDEX]%%|*}] 부터 이어하시겠습니까? (y/n): " choice
                if [[ "$choice" == [Yy]* ]]; then
                    START_INDEX=$NEXT_INDEX
                    echo "  -> 선택하신 실험부터 이어하기를 진행합니다."
                else
                    START_INDEX=0
                    echo "  -> 기존 기록을 무시하고 처음(0번)부터 새로 시작합니다."
                fi
            fi
        else
            echo "========================================"
            read -p "💡 비정상 종료된 실험 [${EXPS[$MATCHED_INDEX]%%|*}] 을 감지했습니다. 해당 구간부터 다시 이어하시겠습니까? (y/n): " choice
            if [[ "$choice" == [Yy]* ]]; then
                START_INDEX=$MATCHED_INDEX
                echo "  🗑️ 미완료된 기존 로그를 삭제하고 다시 시작합니다: $(basename "$NEWEST_LOG")"
                rm -f "$NEWEST_LOG"
            else
                START_INDEX=0
                echo "  -> 기존 기록을 무시하고 처음(0번)부터 새로 시작합니다."
            fi
        fi
    fi
fi

echo "========================================"
echo "  Write Stall 실험 시작"
echo "  로그 저장: ${LOG_DIR}"
echo "========================================"

run_experiment() {
    local exp_name=$1
    local extra_args=$2
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local log_file="${LOG_DIR}/${exp_name}_${timestamp}.log"

    local thread_count=$(echo "$extra_args" | sed -n 's/.*--threads=\([0-9]*\).*/\1/p')
    if [ -z "$thread_count" ]; then
        thread_count=1
    fi
    local per_thread_num=$(( NUM_KEYS / thread_count ))

    echo ""
    echo "[진행 중] ${exp_name} (총 ${NUM_KEYS}건 / ${thread_count} Threads -> 스레드당 ${per_thread_num}건) ..."
    rm -rf "${BASE_DB}"
    
    ${DB_BENCH} \
        --benchmarks=fillrandom \
        --db="${BASE_DB}" \
        --num=${per_thread_num} \
        --value_size=${VAL_SIZE} \
        --stats_interval_seconds=1 \
        ${extra_args} > "${log_file}" 2>&1
        
    if [ $? -eq 0 ]; then
        echo "✓ 완료 -> $(basename ${log_file})"
        echo "[EXPERIMENT_COMPLETED]" >> "${log_file}"
    else
        echo "❌ 실패 -> $(basename ${log_file})"
    fi
}

# ── [메인 루프: 무조건 START_INDEX 부터 실행] ──────────
for i in "${!EXPS[@]}"; do
    # 이어하기 시작점(START_INDEX)보다 이전인 실험은 아무 말 없이 조용히 넘어갑니다.
    if [ "$i" -lt "$START_INDEX" ]; then
        continue
    fi

    EXP_NAME="${EXPS[$i]%%|*}"
    EXP_ARGS="${EXPS[$i]#*|}"

    run_experiment "$EXP_NAME" "$EXP_ARGS"
done

rm -rf "${BASE_DB}"

echo ""
echo "[취합] aggregate_stalls.py 실행 중..."
python3 "${ROCKSDB_DIR}/experiment2/aggregate_stalls.py"

echo ""
echo "========================================"
echo "  모든 실험 및 시각화 완료: $(date +"%Y-%m-%d %H:%M:%S")"
echo "========================================"