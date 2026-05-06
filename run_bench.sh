#!/bin/bash

DB_PATH="/tmp/rocksdb_bench"
NUM=100000
READS=50000
VALUE_SIZE=1024

# ── 타임스탬프 생성 ─────────────────────────────────────
TS=$(date +"%Y%m%d_%H%M%S")
RESULT="./experiment/results/${TS}_dbbench_results.csv"

mkdir -p ./experiment/results
echo "workload,cache_mb,hit,miss,hit_rate" > $RESULT

echo "=== db_bench 실험 시작: ${TS} ==="

# ── Step 1. 쓰기 (1회, 캐시 없이) ──────────────────────
echo "[1/2] 데이터 삽입 중..."
rm -rf ${DB_PATH}
./db_bench \
    --benchmarks="fillrandom,compact" \
    --db="${DB_PATH}" \
    --num=${NUM} \
    --value_size=${VALUE_SIZE} \
    --cache_size=0 \
    --use_existing_db=false \
    2>&1 | tail -3
echo "  완료. MemTable 해제됨."

# ── Step 2. 읽기 (캐시 크기별) ──────────────────────────
echo "[2/2] Read 실험 중..."

run_read() {
    local WORKLOAD=$1
    local CACHE_MB=$2
    local LABEL=$3
    local CACHE_BYTES=$((CACHE_MB * 1024 * 1024))

    OUTPUT=$(./db_bench \
        --benchmarks="${WORKLOAD}" \
        --db="${DB_PATH}" \
        --num=${NUM} \
        --reads=${READS} \
        --value_size=${VALUE_SIZE} \
        --cache_size=${CACHE_BYTES} \
        --use_existing_db=true \
        --disable_auto_compactions=true \
        --statistics \
        --stats_dump_period_sec=0 \
        2>&1)

    HIT=$(echo "$OUTPUT"  | grep "rocksdb.block.cache.hit COUNT"  | awk '{print $NF}')
    MISS=$(echo "$OUTPUT" | grep "rocksdb.block.cache.miss COUNT" | awk '{print $NF}')
    HIT=${HIT:-0}; MISS=${MISS:-0}
    TOTAL=$((HIT + MISS))
    RATE=$([ $TOTAL -gt 0 ] && echo "scale=2; $HIT * 100 / $TOTAL" | bc || echo "0.00")

    echo "${LABEL},${CACHE_MB},${HIT},${MISS},${RATE}" >> $RESULT
    echo "  [${LABEL}] ${CACHE_MB}MB → ${RATE}%"
}

for MB in 4 8 16 32 64 128 256; do
    echo "--- Cache: ${MB}MB ---"
    run_read "readrandom" $MB "Uniform"
    run_read "readseq"    $MB "Sequential"
done

# 최신 타임스탬프 저장
echo $TS > ./experiment/results/latest_timestamp.txt

echo ""
echo "✓ 결과 저장: $RESULT"
