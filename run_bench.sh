#!/bin/bash

DB_PATH="/tmp/rocksdb_bench"
NUM=100000
READS=50000
VALUE_SIZE=1024
RESULT="./experiment/results/dbbench_results.csv"

mkdir -p ./experiment/results
echo "workload,cache_mb,hit,miss,hit_rate" > $RESULT

CACHE_SIZES_MB=(4 8 16 32 64 128)

run_experiment() {
    local WORKLOAD=$1
    local CACHE_MB=$2
    local LABEL=$3
    local CACHE_BYTES=$((CACHE_MB * 1024 * 1024))

    rm -rf ${DB_PATH}

    OUTPUT=$(./db_bench \
        --benchmarks="fillrandom,${WORKLOAD}" \
        --db="${DB_PATH}" \
        --num=${NUM} \
        --reads=${READS} \
        --value_size=${VALUE_SIZE} \
        --cache_size=${CACHE_BYTES} \
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

echo "=== db_bench 실험 시작 ==="

for MB in "${CACHE_SIZES_MB[@]}"; do
    echo "--- Cache: ${MB}MB ---"
    run_experiment "readrandom" $MB "Uniform"
    run_experiment "readseq"   $MB "Sequential"
done

echo ""
echo "✓ 결과 저장: $RESULT"
