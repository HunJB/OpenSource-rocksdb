#!/bin/bash
# 단계별 자동 실험 스크립트
#
# 사용법:
#   ./step_experiments.sh [시작] [끝] [단계] [병렬수]
#   ./step_experiments.sh              # 기본: 10→50, 5단계, CPU 코어수 병렬
#   ./step_experiments.sh 10 50 5      # 명시적 지정
#   ./step_experiments.sh 10 50 5 4    # 병렬 4개
#
# 동작:
#   결과 폴더를 초기화하지 않고 누적 방식으로 실험을 추가.
#   각 단계 도달 시 aggregate.py를 실행해 통계 파일 생성.

START=${1:-10}
END=${2:-50}
STEP=${3:-5}
PARALLEL=${4:-$(nproc)}

ROCKSDB_DIR="${HOME}/rocksdb"
EXP_DIR="${ROCKSDB_DIR}/experiment"
BASE_DB="/tmp/rocksdb_exp_db"
LOG_DIR="${EXP_DIR}/results/logs"

echo "========================================"
echo "  단계별 자동 실험"
echo "  범위: ${START}회 → ${END}회 (${STEP}회 단위)"
echo "  병렬: ${PARALLEL}개"
echo "========================================"

cd "${EXP_DIR}"

# ── 빌드 ──────────────────────────────────────────────────
echo ""
echo "[빌드] make clean && make"
make clean && make
if [ $? -ne 0 ]; then
    echo "❌ 빌드 실패. 종료합니다."
    exit 1
fi
mkdir -p "${LOG_DIR}"
echo "✓ 빌드 완료"

# ── DB 쓰기 (1회) ─────────────────────────────────────────
echo ""
echo "[DB 쓰기] writer 실행 중..."
./writer
if [ $? -ne 0 ]; then
    echo "❌ writer 실패. 종료합니다."
    exit 1
fi
echo "✓ DB 쓰기 완료"

# ── 슬롯별 DB 복사 ────────────────────────────────────────
create_db_slot() {
    local slot=$1
    local dst="${BASE_DB}_slot${slot}"
    rm -rf "${dst}"
    cp -al "${BASE_DB}" "${dst}"
    rm -f "${dst}/LOCK" && touch "${dst}/LOCK"
    for f in "${BASE_DB}"/MANIFEST-* "${BASE_DB}"/OPTIONS-* \
              "${BASE_DB}"/CURRENT "${BASE_DB}"/LOG* "${BASE_DB}"/IDENTITY; do
        [ -f "$f" ] && cp --remove-destination "$f" "${dst}/$(basename "$f")" 2>/dev/null || true
    done
}

echo ""
echo "[DB 복사] ${PARALLEL}개 슬롯 생성 중..."
for s in $(seq 0 $((PARALLEL - 1))); do
    create_db_slot "${s}"
done
echo "✓ 슬롯 준비 완료"

# ── 단계별 실험 루프 ──────────────────────────────────────
# 각 단계에서 필요한 실험 수만큼 추가 실행 후 aggregate

run_one() {
    local slot=$1
    local idx=$2
    local slot_db="${BASE_DB}_slot${slot}"
    local run_id
    run_id="$(date +"%Y%m%d_%H%M%S")_$$_s${slot}_${idx}"

    READER_DB_PATH="${slot_db}" READER_RUN_ID="${run_id}" \
        ./reader     >> "${LOG_DIR}/step_${idx}_reader.log" 2>&1
    READER_DB_PATH="${slot_db}" READER_RUN_ID="${run_id}" \
        ./reader_adv >> "${LOG_DIR}/step_${idx}_adv.log"    2>&1
    [ $? -eq 0 ]
}

TOTAL_DONE=0       # 지금까지 완료된 실험 수
GLOBAL_SUCCESS=0
GLOBAL_FAIL=0
STEP_NUM=0

declare -a SLOT_PIDS
for s in $(seq 0 $((PARALLEL - 1))); do SLOT_PIDS[$s]=0; done

# 단계 목록 생성: START, START+STEP, ..., END
TARGETS=()
t=${START}
while [ "${t}" -le "${END}" ]; do
    TARGETS+=("${t}")
    t=$((t + STEP))
done

for TARGET in "${TARGETS[@]}"; do
    STEP_NUM=$((STEP_NUM + 1))
    NEED=$((TARGET - TOTAL_DONE))

    echo ""
    echo "========================================"
    echo "  [단계 ${STEP_NUM}] 목표 ${TARGET}회"
    echo "  추가 실험: ${NEED}회 (현재까지 ${TOTAL_DONE}회)"
    echo "  시각: $(date +"%Y-%m-%d %H:%M:%S")"
    echo "========================================"

    STEP_SUCCESS=0
    STEP_FAIL=0
    STEP_DONE=0

    for i in $(seq 1 "${NEED}"); do
        GLOBAL_IDX=$((TOTAL_DONE + i))
        SLOT=$(( (GLOBAL_IDX - 1) % PARALLEL ))

        # 이 슬롯의 이전 작업 완료 대기
        if [ "${SLOT_PIDS[$SLOT]}" -gt 0 ]; then
            if wait "${SLOT_PIDS[$SLOT]}"; then
                STEP_SUCCESS=$((STEP_SUCCESS + 1))
                GLOBAL_SUCCESS=$((GLOBAL_SUCCESS + 1))
            else
                STEP_FAIL=$((STEP_FAIL + 1))
                GLOBAL_FAIL=$((GLOBAL_FAIL + 1))
            fi
            STEP_DONE=$((STEP_DONE + 1))
        fi

        run_one "${SLOT}" "${GLOBAL_IDX}" &
        SLOT_PIDS[$SLOT]=$!
    done

    # 이번 단계 잔여 슬롯 완료 대기
    for s in $(seq 0 $((PARALLEL - 1))); do
        if [ "${SLOT_PIDS[$s]}" -gt 0 ]; then
            if wait "${SLOT_PIDS[$s]}"; then
                STEP_SUCCESS=$((STEP_SUCCESS + 1))
                GLOBAL_SUCCESS=$((GLOBAL_SUCCESS + 1))
            else
                STEP_FAIL=$((STEP_FAIL + 1))
                GLOBAL_FAIL=$((GLOBAL_FAIL + 1))
            fi
            SLOT_PIDS[$s]=0
            STEP_DONE=$((STEP_DONE + 1))
        fi
    done

    TOTAL_DONE="${TARGET}"
    echo "  ✓ 이번 단계 완료: 성공 ${STEP_SUCCESS}회 / 실패 ${STEP_FAIL}회"

    # ── 이 단계의 통계 취합 ────────────────────────────────
    echo ""
    echo "  [취합] n=${TARGET} 통계 생성 중..."
    python3 aggregate.py "${TARGET}"
    if [ $? -eq 0 ]; then
        echo "  ✓ n=${TARGET} 통계 완료"
    else
        echo "  ❌ aggregate.py 실패 (n=${TARGET})"
    fi
done

# ── DB 슬롯 정리 ──────────────────────────────────────────
for s in $(seq 0 $((PARALLEL - 1))); do
    rm -rf "${BASE_DB}_slot${s}"
done

echo ""
echo "========================================"
echo "  전체 완료"
echo "  총 실험: ${TOTAL_DONE}회"
echo "  성공: ${GLOBAL_SUCCESS}회 / 실패: ${GLOBAL_FAIL}회"
echo "  생성된 통계 파일:"
for TARGET in "${TARGETS[@]}"; do
    ls "${EXP_DIR}/results/aggregated/"*"_n${TARGET}.png" 2>/dev/null \
        | sed 's|.*/||' | sed "s/^/    - /"
done
echo "  완료: $(date +"%Y-%m-%d %H:%M:%S")"
echo "========================================"
