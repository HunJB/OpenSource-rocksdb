#!/bin/bash

# ── 반복 횟수 설정 ─────────────────────────────────────────
REPEAT=${1:-10}   # 인자 없으면 기본 10회
ROCKSDB_DIR="${HOME}/rocksdb"
EXP_DIR="${ROCKSDB_DIR}/experiment"

echo "========================================"
echo "  자동 반복 실험 시작"
echo "  총 반복 횟수: ${REPEAT}회"
echo "========================================"

# ── 최초 1회만 빌드 ────────────────────────────────────────
echo ""
echo "[빌드] make clean && make"
cd ${EXP_DIR}
make clean && make
if [ $? -ne 0 ]; then
    echo "❌ 빌드 실패. 종료합니다."
    exit 1
fi
echo "✓ 빌드 완료"

# ── 실험 반복 ──────────────────────────────────────────────
SUCCESS=0
FAIL=0

for i in $(seq 1 $REPEAT); do
    echo ""
    echo "========================================"
    echo "  실험 ${i} / ${REPEAT} 시작"
    echo "  시각: $(date +"%Y-%m-%d %H:%M:%S")"
    echo "========================================"

    cd ${EXP_DIR}

    # 1. writer 실행
    echo "[1/4] writer 실행 중..."
    ./writer
    if [ $? -ne 0 ]; then
        echo "❌ writer 실패. 이 회차 스킵."
        FAIL=$((FAIL + 1))
        continue
    fi

    # 2. reader 실행
    echo "[2/4] reader 실행 중..."
    ./reader
    if [ $? -ne 0 ]; then
        echo "❌ reader 실패. 이 회차 스킵."
        FAIL=$((FAIL + 1))
        continue
    fi

    # 3. run_bench.sh 실행
    echo "[3/4] run_bench.sh 실행 중..."
    ./run_bench.sh
    if [ $? -ne 0 ]; then
        echo "❌ run_bench 실패. 이 회차 스킵."
        FAIL=$((FAIL + 1))
        continue
    fi

    # 4. plot.py 실행 (그래프 저장, 화면 출력 없이)
    echo "[4/4] plot.py 실행 중..."
    python3 plot.py
    if [ $? -ne 0 ]; then
        echo "❌ plot.py 실패. 이 회차 스킵."
        FAIL=$((FAIL + 1))
        continue
    fi

    SUCCESS=$((SUCCESS + 1))
    echo ""
    echo "✓ 실험 ${i} / ${REPEAT} 완료"

    # 진행률 표시
    PROGRESS=$((SUCCESS * 100 / REPEAT))
    echo "  진행률: ${SUCCESS}/${REPEAT} (${PROGRESS}%)"
    echo "  성공: ${SUCCESS}회 / 실패: ${FAIL}회"

    # 실험 간 잠시 대기 (타임스탬프 겹침 방지)
    sleep 2
done

# ── 전체 실험 완료 후 취합 ─────────────────────────────────
echo ""
echo "========================================"
echo "  전체 실험 완료"
echo "  성공: ${SUCCESS}회 / 실패: ${FAIL}회"
echo "========================================"

if [ $SUCCESS -gt 0 ]; then
    echo ""
    echo "[취합] aggregate.py 실행 중..."
    cd ${EXP_DIR}
    python3 aggregate.py
    if [ $? -eq 0 ]; then
        echo "✓ 취합 완료"
        echo ""
        echo "결과 위치:"
        echo "  데이터: ${EXP_DIR}/results/exp_data/"
        echo "  그래프: ${EXP_DIR}/results/graph/"
    else
        echo "❌ aggregate.py 실패"
    fi
else
    echo "❌ 성공한 실험이 없어 취합을 생략합니다."
fi

echo ""
echo "========================================"
echo "  모든 작업 완료: $(date +"%Y-%m-%d %H:%M:%S")"
echo "========================================"