#!/bin/bash
# 반복 실험 자동화 (슬롯 기반 병렬 실행, reader + reader_adv 동일 폴더 저장)
#
# 사용법:
#   ./run_experiments.sh [반복횟수] [병렬수] [옵션]
#   ./run_experiments.sh 1000          # 1000회, CPU 코어수 병렬
#   ./run_experiments.sh 1000 4        # 1000회, 4개 병렬
#   ./run_experiments.sh 100 2 --bench # bench도 실행 (1회)
#
# 병렬화 전략:
#   - writer는 최초 1회만 실행 (항상 동일한 데이터)
#   - DB를 PARALLEL개 복사 (SST는 hard link → 추가 디스크 사용 없음)
#   - 각 슬롯(0..PARALLEL-1)이 고유한 DB 경로를 독점 사용
#   - 슬롯마다 READER_RUN_ID를 고정하여 reader/reader_adv가 같은 폴더에 저장
#   - 슬롯이 비면 다음 실험이 그 슬롯을 이어받음

REPEAT=${1:-10}
PARALLEL=${2:-$(nproc)}
RUN_BENCH=false
for arg in "$@"; do
    [ "$arg" = "--bench" ] && RUN_BENCH=true
done

ROCKSDB_DIR="${HOME}/rocksdb"
EXP_DIR="${ROCKSDB_DIR}/experiment"
LOG_DIR="${EXP_DIR}/results/logs"
BASE_DB="/tmp/rocksdb_exp_db"

echo "========================================"
echo "  자동 반복 실험"
echo "  반복: ${REPEAT}회 / 병렬: ${PARALLEL}개"
[ "${RUN_BENCH}" = true ] && echo "  Bench: 활성화 (1회)"
echo "========================================"

cd "${EXP_DIR}"

# ── 빌드 (최초 1회) ────────────────────────────────────────
echo ""
echo "[빌드] make clean && make"
make clean && make
if [ $? -ne 0 ]; then
    echo "❌ 빌드 실패. 종료합니다."
    exit 1
fi
mkdir -p "${LOG_DIR}"
echo "✓ 빌드 완료"

# ── DB 쓰기 (최초 1회만) ───────────────────────────────────
echo ""
echo "[DB 쓰기] 최초 1회 실행..."
./writer
if [ $? -ne 0 ]; then
    echo "❌ writer 실패. 종료합니다."
    exit 1
fi
echo "✓ DB 쓰기 완료"

# ── 슬롯별 DB 복사본 생성 ──────────────────────────────────
# SST 파일: hard link (추가 디스크 사용 없음)
# LOCK/MANIFEST 등 가변 파일: 복사 (독립 잠금 보장)
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
echo "[DB 복사] ${PARALLEL}개 슬롯 생성 중 (hard link)..."
for s in $(seq 0 $((PARALLEL - 1))); do
    create_db_slot "${s}"
done
echo "✓ 슬롯 준비 완료"

# ── 슬롯 기반 병렬 실험 실행 ──────────────────────────────
# 각 슬롯에서 reader + reader_adv를 순서대로 실행 (같은 READER_RUN_ID 공유)
run_slot() {
    local slot=$1
    local idx=$2
    local slot_db="${BASE_DB}_slot${slot}"
    local run_id
    run_id="$(date +"%Y%m%d_%H%M%S")_$$_s${slot}"

    READER_DB_PATH="${slot_db}" \
    READER_RUN_ID="${run_id}" \
        ./reader  >> "${LOG_DIR}/run_${idx}_reader.log"  2>&1
    local rc_reader=$?

    READER_DB_PATH="${slot_db}" \
    READER_RUN_ID="${run_id}" \
        ./reader_adv >> "${LOG_DIR}/run_${idx}_adv.log" 2>&1
    local rc_adv=$?

    [ $rc_reader -eq 0 ] && [ $rc_adv -eq 0 ]
}

echo ""
echo "[Reader+Adv] ${REPEAT}회 병렬 실행 중 (병렬=${PARALLEL})..."

SUCCESS=0
FAIL=0
COMPLETED=0
declare -a SLOT_PIDS
for s in $(seq 0 $((PARALLEL - 1))); do
    SLOT_PIDS[$s]=0
done

for i in $(seq 1 "${REPEAT}"); do
    SLOT=$(( (i - 1) % PARALLEL ))

    # 이 슬롯의 이전 작업이 끝날 때까지 대기
    if [ "${SLOT_PIDS[$SLOT]}" -gt 0 ]; then
        if wait "${SLOT_PIDS[$SLOT]}"; then
            SUCCESS=$((SUCCESS + 1))
        else
            FAIL=$((FAIL + 1))
        fi
        COMPLETED=$((COMPLETED + 1))
        if [ $((COMPLETED % 10)) -eq 0 ] || [ "${COMPLETED}" -eq "${REPEAT}" ]; then
            echo "  진행: ${COMPLETED}/${REPEAT}  (성공 ${SUCCESS} / 실패 ${FAIL})"
        fi
    fi

    run_slot "${SLOT}" "${i}" &
    SLOT_PIDS[$SLOT]=$!
done

# 잔여 슬롯 완료 대기
for s in $(seq 0 $((PARALLEL - 1))); do
    if [ "${SLOT_PIDS[$s]}" -gt 0 ]; then
        if wait "${SLOT_PIDS[$s]}"; then
            SUCCESS=$((SUCCESS + 1))
        else
            FAIL=$((FAIL + 1))
        fi
        COMPLETED=$((COMPLETED + 1))
    fi
done

echo ""
echo "✓ 실험 완료: 성공 ${SUCCESS}회 / 실패 ${FAIL}회"

# ── DB 슬롯 정리 ──────────────────────────────────────────
for s in $(seq 0 $((PARALLEL - 1))); do
    rm -rf "${BASE_DB}_slot${s}"
done

# ── (선택) Bench 1회만 실행 ────────────────────────────────
if [ "${RUN_BENCH}" = true ]; then
    echo ""
    echo "[Bench] run_bench.sh 실행 중 (1회)..."
    ./run_bench.sh
    if [ $? -ne 0 ]; then
        echo "⚠ bench 실패 (계속 진행)"
    else
        echo "✓ bench 완료"
    fi
fi

# ── 취합 ──────────────────────────────────────────────────
if [ "${SUCCESS}" -gt 0 ]; then
    echo ""
    echo "[취합] aggregate.py 실행 중..."
    python3 aggregate.py
    if [ $? -eq 0 ]; then
        echo "✓ 취합 완료"
    else
        echo "❌ aggregate.py 실패"
    fi
else
    echo "❌ 성공한 실험이 없어 취합을 생략합니다."
fi

echo ""
echo "========================================"
echo "  완료: $(date +"%Y-%m-%d %H:%M:%S")"
echo "  성공: ${SUCCESS}회 / 실패 ${FAIL}회"
echo "  결과: ${EXP_DIR}/results/"
echo "========================================"
