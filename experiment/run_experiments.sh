#수정 : adv도 수행에 포함, 같은 타임스탬프 디렉토리 안에 결과 함께 생성되도록 수행
#!/bin/bash

# ── 반복 횟수 설정 ─────────────────────────────────────────
REPEAT=${1:-10}   # 인자 없으면 기본 10회
ROCKSDB_DIR="${HOME}/rocksdb"
EXP_DIR="${ROCKSDB_DIR}/experiment"

echo "========================================"
echo "  자동 반복 실험 시작 (Normal + Advanced)"
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
    # 해당 회차의 고정 타임스탬프 생성 (폴더 갈라짐 방지 핵심)
    FIXED_TS=$(date +"%Y%m%d_%H%M%S")

    echo ""
    echo "========================================"
    echo "  실험 ${i} / ${REPEAT} 시작"
    echo "  시각: $(date +"%Y-%m-%d %H:%M:%S")"
    echo "  ID: ${FIXED_TS}"
    echo "========================================"

    cd ${EXP_DIR}

    # 1. writer 실행
    echo "[1/5] writer 실행 중..."
    ./writer
    if [ $? -ne 0 ]; then
        echo "❌ writer 실패. 이 회차 스킵."
        FAIL=$((FAIL + 1))
        continue
    fi

    # 2. reader 실행 (고정 TS 전달)
    echo "[2/5] reader 실행 중..."
    ./reader $FIXED_TS
    if [ $? -ne 0 ]; then
        echo "❌ reader 실패. 이 회차 스킵."
        FAIL=$((FAIL + 1))
        continue
    fi

    # 3. reader_adv 실행 (고정 TS 전달)
    echo "[3/5] reader_adv 실행 중..."
    ./reader_adv $FIXED_TS
    if [ $? -ne 0 ]; then
        echo "❌ reader_adv 실패. 이 회차 스킵."
        FAIL=$((FAIL + 1))
        continue
    fi

    # 4. run_bench.sh 실행 (고정 TS 전달)
    echo "[4/5] run_bench.sh 실행 중..."
    ./run_bench.sh $FIXED_TS
    if [ $? -ne 0 ]; then
        echo "❌ run_bench 실패. 이 회차 스킵."
        FAIL=$((FAIL + 1))
        continue
    fi

    # 5. plot.py 실행 (고정 TS 전달)
    echo "[5/5] plot.py 실행 중..."
    python3 plot.py $FIXED_TS
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
    else
        echo "❌ aggregate.py 실패"
    fi
fi
