#!/bin/bash

DB_PATH="/tmp/rocksdb_bench"
NUM=100000
READS=50000
VALUE_SIZE=1024
RESULT="./experiment/results/dbbench_results.csv"

mkdir -p ./experiment/results
echo "workload,cache_mb,hit,miss,hit_rate" > $RESULT

CACHE_SIZES_MB=(4 8 16 32 64 128 256)

# ── Step 1. 쓰기 전용 실행 (1회만, 캐시 없이) ──────────────
echo "=== [1/2] 데이터 삽입 중 (fillrandom) ==="
rm -rf ${DB_PATH}

./db_bench \
    --benchmarks="fillrandom,compact" \
    --db="${DB_PATH}" \
    --num=${NUM} \
    --value_size=${VALUE_SIZE} \
    --cache_size=0 \
    --disable_auto_compactions=false \
    --use_existing_db=false \
    2>&1 | tail -3

# 프로세스 종료 → MemTable 완전 해제
echo "  완료. MemTable 해제됨."
echo ""

# ── Step 2. 읽기 전용 실행 (캐시 크기별 반복) ─────────────
echo "=== [2/2] 캐시 크기별 Read 실험 ==="

run_read() {
    local WORKLOAD=$1    # readrandom / readseq
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
    HIT=${HIT:-0}
    MISS=${MISS:-0}
    TOTAL=$((HIT + MISS))

    if [ $TOTAL -gt 0 ]; then
        RATE=$(echo "scale=2; $HIT * 100 / $TOTAL" | bc)
    else
        RATE="0.00"
    fi

    echo "${LABEL},${CACHE_MB},${HIT},${MISS},${RATE}" >> $RESULT
    echo "  [${LABEL}] cache=${CACHE_MB}MB → Hit=${HIT}, Miss=${MISS}, Rate=${RATE}%"
}

for MB in "${CACHE_SIZES_MB[@]}"; do
    echo "--- Cache: ${MB}MB ---"
    run_read "readrandom" $MB "Uniform"
    run_read "readseq"    $MB "Sequential"
done

echo ""
echo "✓ 결과 저장: $RESULT"
